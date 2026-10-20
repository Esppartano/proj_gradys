"""
Parâmetros do cenário Swarm Core e dos protocolos (todos os ajustáveis num só lugar).

Geometria (ver `scenario.py`):
- Core em V com 9 nós, ápice à frente, girando devagar em torno de CENTER.
- Vizinhos diretos a L m; alcance de rádio D = L + ε (só os vizinhos diretos).
- Satélites patrulham seu setor (0/90/180/270°) numa órbita (shell) com o
  raio do seu lado do V e se acoplam (tandem) quando o lado passa pelo setor.
- BS no centro, com antena de maior alcance (D_BS) que cobre a asa interna.
"""
from math import pi, radians

# ── Simulação ──────────────────────────────────────────────────────────────
SIMULATION_DURATION = 400.0   # s (≈ 3,3 voltas do Core)
MOBILITY_UPDATE = 0.05        # s entre atualizações de posição (telemetria)

# ── Rádio ──────────────────────────────────────────────────────────────────
L = 5.0                       # m entre vizinhos diretos na formação
EPSILON = 1.0                 # m de folga
COMM_RANGE = L + EPSILON      # D: só alcança os vizinhos diretos
BS_RANGE = 22.0               # D_BS: antena da BS (cobre a asa interna, não o ápice)
COMM_DELAY = 0.01             # s por transmissão

# ── Formação em V (Swarm Core) ─────────────────────────────────────────────
CENTER = (0.0, 0.0)
BS_ALT = 2.0
CORE_ALT = 10.0
SATELLITE_ALT = 12.0          # 2 m acima do Core: no tandem ouve o hub e os vizinhos dele
APEX_RADIUS = 25.0            # R: raio do circuito do ápice
V_HALF_ANGLE = radians(45)    # abertura de cada asa (≥ 37° para as asas não se ouvirem)
ROTATION_PERIOD = 120.0       # s por volta ("slowly revolves")
ROTATION_OMEGA = 2 * pi / ROTATION_PERIOD
CORE_SPEED = 6.0              # m/s máx. (folga para corrigir o atraso do seguidor)

# ── Camada de enlace / formação (igual para todos os protocolos) ──────────
LINK_BEACON = {"core": 0.2, "satellite": 0.5, "bs": 1.0}  # s entre beacons de enlace
LINK_TIMEOUT = 1.5            # s sem beacon → vizinho fora de alcance

# ── Satélites ──────────────────────────────────────────────────────────────
SATELLITE_SPEED = 5.0         # m/s
# Satélite → (ângulo do setor em graus, nó do Core que define o seu lado/shell)
SATELLITE_SECTORS = {
    10: (0, 5),     # S1: ponta externa (C5)
    11: (90, 5),    # S2: ponta externa (C5)
    12: (180, 1),   # S3: ápice (C1)
    13: (270, 1),   # S4: ápice (C1)
}
PATROL_ARC = radians(12)      # ± arco de patrulha livre em torno do setor
PATROL_RADIAL = 3.0           # ± m de patrulha radial em torno do shell
APPROACH_LEAD = 10.0          # s antes da passagem prevista: começa a aproximação
HANDSHAKE_WAIT = 0.6          # s ouvindo candidatos antes de escolher o hub
TANDEM_T = 5.0                # tandem dura entre T e 4T s
MOBILITY_SEED = 7             # sementes por nó: mobilidade idêntica em todos os protocolos

# ── Tráfego (igual para todos os protocolos) ───────────────────────────────
TRAFFIC_SEED = 42
TRAFFIC_INTERVAL = (4.0, 10.0)  # s entre envios de cada origem
TRAFFIC_START = 3.0
TRAFFIC_END = 240.0           # s: deixa ≥ 1 volta para as últimas mensagens chegarem

# ── Protocolos ─────────────────────────────────────────────────────────────
FLOOD_TTL = 10                # diâmetro: satélite → ponta → ... → ponta → BS

GEO_DEST_RADIUS = 10.0        # m: raio da zona-alvo (esfera) em torno da posição prevista do destino

DTN_BUFFER_SIZE = 200
DTN_MSG_TTL = 250.0           # s após a criação: a cópia expira (> 2 voltas do Core)

SWCORE_HOLD_TIME = 150.0      # s que um nó do Core guarda mensagem sem rota (> 1 volta)

# ── Energia (unidades arbitrárias; mobilidade é igual em todos) ───────────
E_TX = 1.0
E_RX = 0.5

# ── Visualização (modo 3D) ─────────────────────────────────────────────────
EVENT_LOG = True
EVENT_HIGHLIGHT_S = 1.5
VIZ_NODE_SIZE = 1.5
