"""
Cenário Swarm Core: papéis dos nós, geometria da formação e tráfego.

Funções puras (sem GrADySim), usadas pelo nó para decidir para onde voar e
pela orquestração para criar os nós.

IDs: 0 = torre terrestre, 1..9 = Core em V (C1..C9), 10..13 = satélites (S1..S4).
"""
from math import atan2, cos, sin
from typing import List, Tuple

from src.config import (
    CENTER, CORE_ALT, COVER_NODE, COVER_START, MISSION_TRAFFIC, RONDA_END,
    RONDA_NODE, ROTATION_OMEGA, SATELLITE_ALT, SATELLITE_OMEGA,
    SATELLITE_ORBIT_RADIUS, SATELLITE_PHASES, TELEMETRY_END, TELEMETRY_INTERVAL,
    TELEMETRY_START, TOWER_ALT, V_SLOTS,
)

Position = Tuple[float, float, float]

TOWER = 0
CORE = list(range(1, 10))
SATELLITES = list(range(10, 14))
ALL_NODES = [TOWER] + CORE + SATELLITES


def label(node_id: int) -> str:
    if node_id == TOWER:
        return "Torre"
    if node_id in CORE:
        return f"C{node_id}"
    return f"S{node_id - 9}"


def role(node_id: int) -> str:
    if node_id == TOWER:
        return "tower"
    return "core" if node_id in CORE else "satellite"


# ── Geometria ──────────────────────────────────────────────────────────────

def slot_position(slot: int, t: float) -> Position:
    """Posição do slot da formação em V no instante t (referencial girante)."""
    u, v = V_SLOTS[slot]
    a = ROTATION_OMEGA * t
    return (
        CENTER[0] + u * cos(a) + v * sin(a),
        CENTER[1] + u * sin(a) - v * cos(a),
        CORE_ALT,
    )


def core_slot(node_id: int, t: float) -> int:
    """Slot ocupado por um nó do Core (C5 cobre o slot de C4 durante a ronda)."""
    if node_id == COVER_NODE and COVER_START <= t < RONDA_END:
        return RONDA_NODE
    return node_id


def orbit_position(phase: float, t: float) -> Position:
    a = phase + SATELLITE_OMEGA * t
    return (
        CENTER[0] + SATELLITE_ORBIT_RADIUS * cos(a),
        CENTER[1] + SATELLITE_ORBIT_RADIUS * sin(a),
        SATELLITE_ALT,
    )


def orbit_phase_at(position: Position, t: float) -> float:
    """Fase orbital que coloca o satélite na posição dada no instante t."""
    angle = atan2(position[1] - CENTER[1], position[0] - CENTER[0])
    return angle - SATELLITE_OMEGA * t


def initial_position(node_id: int) -> Position:
    if node_id == TOWER:
        return (CENTER[0], CENTER[1], TOWER_ALT)
    if node_id in CORE:
        return slot_position(node_id, 0.0)
    if node_id == 10:  # S1 começa em tandem sobre C5
        x, y, _ = slot_position(5, 0.0)
        return (x, y, SATELLITE_ALT)
    return orbit_position(SATELLITE_PHASES[node_id], 0.0)


# ── Tráfego ────────────────────────────────────────────────────────────────

def traffic() -> List[Tuple[float, int, int, str]]:
    """Todas as mensagens da simulação: (instante, origem, destino, rótulo)."""
    flows = list(MISSION_TRAFFIC)
    for sat in SATELLITES:
        t = TELEMETRY_START + (sat - SATELLITES[0])
        n = 1
        while t <= TELEMETRY_END:
            flows.append((t, sat, TOWER, f"TELEM_{label(sat)}_{n}"))
            t += TELEMETRY_INTERVAL
            n += 1
    return sorted(flows)
