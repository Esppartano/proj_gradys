"""
Cenário Swarm Core: papéis, plano de voo compartilhado e árvore.

Funções puras (sem GrADySim). O "plano compartilhado" é o que cada nó sabe
antes da missão (não é conhecimento global em tempo de execução):
- a geometria do V e a lei de rotação (o líder voa por ela);
- o eixo e o ponto de acoplamento de cada satélite (o GeoCast usa como
  posição prevista do destino).

IDs: 0..8 = Core (C1 ápice, C2..C5 asa direita, C6..C9 asa esquerda),
9..12 = satélites (S1 leste, S2 norte, S3 oeste, S4 sul).
"""
from math import cos, hypot, radians, sin
from typing import Dict, List, Tuple

from src.config import (
    AWAY_DISTANCE, CENTER, CORE_ALT, DOCK_MARGIN, L, ROTATION_OMEGA,
    SATELLITE_ALT, SATELLITE_AXES, V_HALF_ANGLE,
)

Position = Tuple[float, float, float]

CORE = list(range(0, 9))
SATELLITES = list(range(9, 13))
ENDPOINTS = SATELLITES
ALL_NODES = CORE + SATELLITES
APEX = 0

# Árvore geradora do Core (já criada): as arestas do V
TREE_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8)]
TREE_NEIGHBORS: Dict[int, List[int]] = {n: [] for n in CORE}
for _a, _b in TREE_EDGES:
    TREE_NEIGHBORS[_a].append(_b)
    TREE_NEIGHBORS[_b].append(_a)
# Líder de mobilidade de cada nó (cascata pela árvore; o ápice não segue ninguém)
FORMATION_PARENT = {1: 0, 2: 1, 3: 2, 4: 3, 5: 0, 6: 5, 7: 6, 8: 7}


def label(node_id: int) -> str:
    if node_id in CORE:
        return f"C{node_id + 1}"
    return f"S{node_id - 8}"


def role(node_id: int) -> str:
    return "core" if node_id in CORE else "satellite"


# ── Geometria do V (referencial que gira com a formação) ──────────────────
#   u = lateral (perpendicular ao eixo do V); v = recuo atrás do ápice, ao longo
#   do eixo. A origem é o centroide do V: a formação gira em torno dele, e as
#   duas pontas (C5 e C9), simétricas em relação ao eixo, ficam à mesma
#   distância do centro — são as extremidades que varrem o perímetro.

_DU, _DV = L * sin(V_HALF_ANGLE), L * cos(V_HALF_ANGLE)
_CENTROID_V = _DV * 2 * (1 + 2 + 3 + 4) / 9  # recuo médio dos 9 nós
V_SLOTS: Dict[int, Tuple[float, float]] = {APEX: (0.0, -_CENTROID_V)}
for _k in range(1, 5):
    V_SLOTS[_k] = (_k * _DU, _k * _DV - _CENTROID_V)        # asa direita: C2..C5
    V_SLOTS[4 + _k] = (-_k * _DU, _k * _DV - _CENTROID_V)   # asa esquerda: C6..C9


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


# Perímetro externo varrido pela rotação: o raio do nó mais afastado do centro
PERIMETER_RADIUS = max(hypot(*uv) for uv in V_SLOTS.values())
DOCK_RADIUS = PERIMETER_RADIUS + DOCK_MARGIN


# ── Satélites ──────────────────────────────────────────────────────────────

def axis_point(sat: int, radius: float) -> Position:
    angle = radians(SATELLITE_AXES[sat])
    return (CENTER[0] + radius * cos(angle), CENTER[1] + radius * sin(angle), SATELLITE_ALT)


def satellite_dock(sat: int) -> Position:
    """Ponto de acoplamento: no eixo do satélite, 5 m além do perímetro."""
    return axis_point(sat, DOCK_RADIUS)


def satellite_away(sat: int) -> Position:
    """Ponto de afastamento: mais para fora, no mesmo eixo."""
    return axis_point(sat, DOCK_RADIUS + AWAY_DISTANCE)


def planned_position(node_id: int) -> Position:
    """Posição que o plano compartilhado atribui a um satélite (usada pelo GeoCast)."""
    return satellite_dock(node_id)


def initial_position(node_id: int) -> Position:
    if node_id in CORE:
        return slot_position(node_id, 0.0)
    return satellite_dock(node_id)
