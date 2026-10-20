"""
Cenário Swarm Core: papéis, plano de voo compartilhado, árvore e tráfego.

Funções puras (sem GrADySim). O "plano compartilhado" é o que cada nó sabe
antes da missão (não é conhecimento global em tempo de execução):
- a geometria do V e a lei de rotação (o líder voa por ela; os satélites a
  usam para prever quando o seu lado passa pelo setor);
- o setor/shell de cada satélite e a posição da BS (o GeoCast usa como
  posição prevista do destino).

IDs: 0 = BS, 1..9 = Core (C1 ápice, C2..C5 asa externa, C6..C9 asa interna),
10..13 = satélites (S1..S4).
"""
import random
from functools import lru_cache
from math import atan2, cos, hypot, pi, radians, sin
from typing import Dict, List, Tuple

from src.config import (
    APEX_RADIUS, BS_ALT, CENTER, CORE_ALT, L, ROTATION_OMEGA, SATELLITE_ALT,
    SATELLITE_SECTORS, TRAFFIC_END, TRAFFIC_INTERVAL, TRAFFIC_SEED, TRAFFIC_START,
    V_HALF_ANGLE,
)

Position = Tuple[float, float, float]

BS = 0
CORE = list(range(1, 10))
SATELLITES = list(range(10, 14))
ENDPOINTS = [BS] + SATELLITES
ALL_NODES = [BS] + CORE + SATELLITES

# Árvore geradora do Core (já criada): as arestas do V
TREE_EDGES = [(1, 2), (2, 3), (3, 4), (4, 5), (1, 6), (6, 7), (7, 8), (8, 9)]
TREE_NEIGHBORS: Dict[int, List[int]] = {n: [] for n in CORE}
for _a, _b in TREE_EDGES:
    TREE_NEIGHBORS[_a].append(_b)
    TREE_NEIGHBORS[_b].append(_a)
# Líder de mobilidade de cada nó (cascata pela árvore; C1 não segue ninguém)
FORMATION_PARENT = {2: 1, 3: 2, 4: 3, 5: 4, 6: 1, 7: 6, 8: 7, 9: 8}


def label(node_id: int) -> str:
    if node_id == BS:
        return "BS"
    if node_id in CORE:
        return f"C{node_id}"
    return f"S{node_id - 9}"


def role(node_id: int) -> str:
    if node_id == BS:
        return "bs"
    return "core" if node_id in CORE else "satellite"


# ── Geometria do V (referencial que gira com a formação) ──────────────────
#   u = distância radial ao centro; v = recuo atrás do ápice, ao longo da tangente.

_DU, _DV = L * sin(V_HALF_ANGLE), L * cos(V_HALF_ANGLE)
V_SLOTS: Dict[int, Tuple[float, float]] = {1: (APEX_RADIUS, 0.0)}
for _k in range(1, 5):
    V_SLOTS[1 + _k] = (APEX_RADIUS + _k * _DU, _k * _DV)   # asa externa
    V_SLOTS[5 + _k] = (APEX_RADIUS - _k * _DU, _k * _DV)   # asa interna


def to_world(u: float, v: float, angle: float) -> Tuple[float, float]:
    """Vetor (u, v) do referencial girante → (x, y) do mundo (sem o centro)."""
    return u * cos(angle) + v * sin(angle), u * sin(angle) - v * cos(angle)


def formation_angle(t: float) -> float:
    return ROTATION_OMEGA * t


def slot_position(slot: int, t: float) -> Position:
    """Posição planejada do slot no instante t."""
    x, y = to_world(*V_SLOTS[slot], formation_angle(t))
    return (CENTER[0] + x, CENTER[1] + y, CORE_ALT)


def rotate(position: Position, angle: float) -> Position:
    """Gira a posição em torno de CENTER (sentido da formação)."""
    x, y = position[0] - CENTER[0], position[1] - CENTER[1]
    c, s = cos(angle), sin(angle)
    return (CENTER[0] + x * c - y * s, CENTER[1] + x * s + y * c, position[2])


def slot_offset(child: int, parent: int, angle: float) -> Tuple[float, float]:
    """Deslocamento (x, y) do filho em relação ao pai na formação."""
    (uc, vc), (up, vp) = V_SLOTS[child], V_SLOTS[parent]
    return to_world(uc - up, vc - vp, angle)


def slot_radius(slot: int) -> float:
    return hypot(*V_SLOTS[slot])


def next_pass(slot: int, sector_angle: float, t: float) -> float:
    """Próximo instante ≥ t em que o slot passa pelo ângulo do setor (plano)."""
    u, v = V_SLOTS[slot]
    phase = atan2(-v, u)
    delta = (sector_angle - phase - formation_angle(t)) % (2 * pi)
    return t + delta / ROTATION_OMEGA


# ── Satélites e BS ─────────────────────────────────────────────────────────

def satellite_side(sat: int) -> int:
    return SATELLITE_SECTORS[sat][1]


def satellite_home(sat: int, d_angle: float = 0.0, d_radius: float = 0.0) -> Position:
    """Ponto do setor do satélite no seu shell (com desvio opcional de patrulha)."""
    angle = radians(SATELLITE_SECTORS[sat][0]) + d_angle
    r = slot_radius(satellite_side(sat)) + d_radius
    return (CENTER[0] + r * cos(angle), CENTER[1] + r * sin(angle), SATELLITE_ALT)


def planned_position(node_id: int) -> Position:
    """Posição que o plano compartilhado atribui a um endpoint (usada pelo GeoCast)."""
    if node_id == BS:
        return (CENTER[0], CENTER[1], BS_ALT)
    return satellite_home(node_id)


def initial_position(node_id: int) -> Position:
    if node_id == BS:
        return (CENTER[0], CENTER[1], BS_ALT)
    if node_id in CORE:
        return slot_position(node_id, 0.0)
    return satellite_home(node_id)


# ── Tráfego ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def traffic() -> List[Tuple[float, int, int, str]]:
    """Todas as mensagens: (instante, origem, destino, rótulo).

    Satélite → outro satélite ou BS (sorteado); BS → satélite sorteado
    (comando). A semente fixa dá o MESMO tráfego a todos os protocolos.
    """
    rng = random.Random(TRAFFIC_SEED)
    flows = []
    for src in ENDPOINTS:
        targets = SATELLITES if src == BS else [n for n in ENDPOINTS if n != src]
        t, n = TRAFFIC_START + rng.uniform(*TRAFFIC_INTERVAL), 1
        while t <= TRAFFIC_END:
            dst = rng.choice([d for d in targets if d != src])
            flows.append((round(t, 2), src, dst, f"{label(src)}>{label(dst)}#{n}"))
            t += rng.uniform(*TRAFFIC_INTERVAL)
            n += 1
    return sorted(flows)
