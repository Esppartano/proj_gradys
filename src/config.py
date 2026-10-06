"""
Parâmetros do cenário Swarm Core e dos protocolos (padrão do template:
todos os parâmetros ajustáveis num só lugar).
"""
from math import pi

# ── Simulação ──────────────────────────────────────────────────────────────
SIMULATION_DURATION = 40.0    # s

# ── Rádio ──────────────────────────────────────────────────────────────────
COMM_RANGE = 40.0             # m
COMM_DELAY = 0.01             # s por transmissão

# ── Formação em V (Swarm Core) ─────────────────────────────────────────────
CENTER = (25.0, 0.0)          # centro de rotação = posição XY da torre
TOWER_ALT = 5.0
CORE_ALT = 15.0
SATELLITE_ALT = 17.5
ROTATION_PERIOD = 22.0        # s por volta completa
ROTATION_OMEGA = 2 * pi / ROTATION_PERIOD   # ≈ 0,2856 rad/s
CORE_SPEED = 14.0             # m/s (teto para a asa externa acompanhar a rotação)
STEP_INTERVAL = 0.4           # s entre atualizações de destino da formação

# Coordenadas de cada slot no referencial que gira com a formação:
#   u = distância radial ao centro; v = recuo atrás do líder, ao longo da tangente.
# Asas retas com Δu = 2 m e Δv = 5,5 m (abertura total ≈ 40°).
V_SLOTS = {
    1: (34.0, 0.0),   # C1: ápice / líder
    2: (36.0, 5.5),   # C2..C5: asa esquerda (externa)
    3: (38.0, 11.0),
    4: (40.0, 16.5),
    5: (42.0, 22.0),
    6: (32.0, 5.5),   # C6..C9: asa direita (interna)
    7: (30.0, 11.0),
    8: (28.0, 16.5),
    9: (26.0, 22.0),
}

# Revezamento (Formation Flying Control): C4 sai para ronda externa e C5 cobre a vaga.
RONDA_NODE = 4
COVER_NODE = 5
RONDA_START = 12.0            # C4 deixa a formação
COVER_START = 12.5            # C5 assume o slot de C4
RONDA_WAYPOINTS = [           # (instante, x, y, z) da ronda de C4
    (12.0, CENTER[0] - 35.0, CENTER[1] + 35.0, 22.0),
    (16.0, CENTER[0] - 10.0, CENTER[1] + 50.0, 22.0),
]
RONDA_RETURN = 19.0           # C4 voa para interceptar o próprio slot
RONDA_END = 22.0              # C4 reentra; C5 volta à ponta da asa

# ── Satélites ──────────────────────────────────────────────────────────────
SATELLITE_ORBIT_RADIUS = 48.0
SATELLITE_OMEGA = 0.10        # rad/s
SATELLITE_PHASES = {10: -0.48, 11: 1.695, 12: 1.30, 13: 2.78}
# Acoplamentos em tandem: satélite → (hub do Core, início, fim)
TANDEM = {
    10: (5, 0.0, 7.5),        # S1 acompanha C5 no início
    12: (9, 10.0, 12.5),      # S3 acopla em C9
}

# ── Tráfego (igual para todos os protocolos) ───────────────────────────────
# Missão encadeada do Swarm Core original: (instante, origem, destino, rótulo)
MISSION_TRAFFIC = [
    (2.0, 0, 10, "CMD_MISSAO"),
    (6.0, 10, 11, "MSG_S1_S2"),
    (10.5, 12, 11, "MSG_S3_S2"),
    (14.6, 11, 13, "MSG_S2_S4"),
    (23.0, 13, 0, "RELATORIO"),
]
# Telemetria periódica de cada satélite para a torre
TELEMETRY_INTERVAL = 4.0      # s
TELEMETRY_START = 3.0         # s; satélite k começa em START + (k - 10)
TELEMETRY_END = 28.0          # s

# ── Protocolos ─────────────────────────────────────────────────────────────
BEACON_INTERVAL = 1.0         # s (DTN e Árvore Geradora)
NEIGHBOR_TIMEOUT = 2.5        # s sem beacon → vizinho fora de alcance

FLOOD_TTL = 8

GEO_DEST_RADIUS = 15.0        # m: zona de entrega em torno do destino
GEO_ZONE_MARGIN = 15.0        # m: folga da zona de encaminhamento

DTN_BUFFER_SIZE = 200
DTN_MIN_PROGRESS = 5.0        # m
DTN_ACK_TIMEOUT = 2.0         # s

TREE_HOLD_TIME = 15.0         # s que um nó da árvore guarda cópia para satélite ausente

# ── Visualização (modo 3D) ─────────────────────────────────────────────────
EVENT_LOG = True              # imprime eventos de roteamento no terminal
EVENT_HIGHLIGHT_S = 1.5       # s que a cor de um evento permanece no nó
VIZ_NODE_SIZE = 2.5
