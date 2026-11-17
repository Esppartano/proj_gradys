"""
Parâmetros do cenário Swarm Core e dos protocolos (todos os ajustáveis num só lugar).

Geometria (ver `scenario.py`), segundo as convenções da disciplina:
- Core em V com 9 nós a L = 20 m entre vizinhos, girando em torno do próprio
  centro (o centroide do V, em CENTER) com velocidade angular constante: uma
  volta a cada 60 unidades de simulação (60 s). As duas pontas são as extremidades da formação.
- Alcance de rádio de 30 m, igual para o Core e para os satélites. A abertura
  das asas garante que, no Core, só os vizinhos da árvore se ouçam.
- Quatro satélites, um em cada eixo (E, N, W, S), parados 5 m além do
  perímetro varrido pela formação. Acoplam no nó do Core que passa pela linha
  deles, trocam mensagens e se afastam em linha reta pelo próprio eixo.
- Os nós do Core têm armazenamento ilimitado para as mensagens entre satélites.
"""
from math import pi, radians

# ── Simulação: duração e velocidade (ajuste aqui) ──────────────────────────
# 1 volta da formação = ROTATION_PERIOD s simulados = 1 min simulado.
# Logo, TURNS é também a duração em minutos simulados (ex.: TURNS = 60 → 60 min).
# A última volta de cada execução só entrega as pendentes (sem mensagens novas),
# então são necessárias pelo menos 2 voltas para haver mensagens.
ROTATION_PERIOD = 60.0        # s simulados por volta (60 unidades de simulação)
TURNS = 60                    # voltas no modo rápido (python main.py 5: benchmark e resultados)
VIZ_TURNS = 60                # voltas no modo 3D (python main.py <1-4> 1)
VIZ_SPEEDUP = 30.0            # modo 3D: fator de aceleração do tempo na tela.
                              #   1.0 = tempo real (1 volta por minuto); 5.0 = 5× (1 volta em 12 s).
                              #   Não muda a física nem os resultados, só a espera entre eventos.
                              #   O modo rápido não espera o relógio: já roda o mais rápido possível.
SIMULATION_DURATION = TURNS * ROTATION_PERIOD
VIZ_DURATION = VIZ_TURNS * ROTATION_PERIOD
TRAFFIC_END = SIMULATION_DURATION - ROTATION_PERIOD  # o motor recalcula para cada execução
MOBILITY_UPDATE = 0.05        # s entre atualizações de posição (telemetria)

# ── Rádio ──────────────────────────────────────────────────────────────────
L = 20.0                      # m entre vizinhos diretos na formação
COMM_RANGE = 30.0             # m, para o Core e para os satélites
COMM_DELAY = 0.01             # s por transmissão

# ── Formação em V (Swarm Core) ─────────────────────────────────────────────
CENTER = (0.0, 0.0)
CORE_ALT = 10.0
SATELLITE_ALT = 12.0
V_HALF_ANGLE = radians(55)    # abertura de cada asa: nós de asas opostas a ≥ 2·L·sen(55°) ≈ 32,8 m > 30 m
ROTATION_OMEGA = 2 * pi / ROTATION_PERIOD
CORE_SPEED = 15.0             # m/s máx. (as pontas andam a ≈ 7,2 m/s)

# ── Camada de enlace / formação (igual para todos os protocolos) ──────────
LINK_BEACON = {"core": 0.2, "satellite": 0.2}  # s entre beacons de enlace
LINK_TIMEOUT = 1.0            # s sem beacon → vizinho fora de alcance

# ── Satélites ──────────────────────────────────────────────────────────────
SATELLITE_AXES = {9: 0, 10: 90, 11: 180, 12: 270}   # S1 leste, S2 norte, S3 oeste, S4 sul (graus)
SATELLITE_PAIRS = {9: 11, 11: 9, 10: 12, 12: 10}    # pares opostos: leste ↔ oeste, norte ↔ sul
DOCK_MARGIN = 5.0             # m além do perímetro externo da formação
DOCK_CAPTURE = 10.0           # m: acopla no nó do Core que passa pelo ponto (a extremidade), não no 1º que entra no rádio
SATELLITE_SPEED = 5.0         # m/s, constante, só pelo próprio eixo
AWAY_DISTANCE = 40.0          # m que o satélite se afasta pelo eixo após a troca (ida e volta em 16 s)
CONTACT_DWELL = 2.0           # s acoplado trocando mensagens antes de se afastar
CONTACT_GAP = 15.0            # s mínimos entre dois acoplamentos: > janela de contato de uma ponta (≈ 8 s)

# ── Protocolos ─────────────────────────────────────────────────────────────
FLOOD_TTL = 10                # diâmetro: satélite → ponta → ... → outra ponta → satélite

GEO_DEST_RADIUS = 10.0        # m: raio da zona-alvo (esfera) em torno da posição prevista do destino
GEO_SEARCH_MARGIN = 4 * L     # m: a busca de rota pode recuar até isso além da distância do nó preso
SW_HOP_ACK_TIMEOUT = 0.2     # s esperando o HOP_ACK do próximo salto antes de retransmitir (SwCore)

GEO_SEARCH_TIMEOUT = 0.5      # s esperando resposta da busca (ida e volta de ~10 saltos ≈ 0,2 s)

# ── Falha de core (regra do T2) ───────────────────────────────────────────
# A cada FAILURE_PERIOD s, um nó do Core sorteado fica incomunicável (não envia
# nem recebe nada: vizinhos do Core e satélites) por FAILURE_DURATION s. O
# sorteio usa FAILURE_SEED: a mesma sequência de falhas em todos os protocolos.
CORE_FAILURE = True
FAILURE_PERIOD = 30.0         # s entre o início de duas falhas (a 1ª em t = 30 s)
FAILURE_DURATION = 1.0        # s
FAILURE_SEED = 2026

# ── Pub/Sub (T2, ver `pubsub.py`) ──────────────────────────────────────────
PS_TOPICS = ["T1", "T2"]
PS_REGIONS = ["N", "E", "S", "W", "C"]   # região de origem: eixo do satélite ou C (Core)
PS_INTERVAL = 5.0             # s entre sorteios de assinatura/publicação de cada nó
PS_SUBSCRIBE_PROB = 0.05      # chance de uma assinatura nova por sorteio (todos os nós)
PS_PUBLISH_PROB = 0.2         # chance de uma publicação por sorteio (nós do Core; satélites publicam ao acoplar)
PS_SEED = 2026

# ── Energia (unidades arbitrárias; mobilidade é igual em todos) ───────────
E_TX = 1.0
E_RX = 0.5

# ── Visualização (modo 3D) ─────────────────────────────────────────────────
EVENT_LOG = True
EVENT_HIGHLIGHT_S = 1.5 * VIZ_SPEEDUP  # s simulados = ≈ 1,5 s na tela, qualquer que seja o fator
VIZ_NODE_SIZE = 4.0
