"""
Motor: monta e roda a simulação de um único cenário (Swarm Core em V);
só o protocolo muda. O ponto de entrada é o menu em `main.py`, na raiz.
"""
from typing import Dict, List

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.config import COMM_DELAY, COMM_RANGE, SIMULATION_DURATION
from src.metrics import METRICS
from src.node import LOCATIONS
from src.nodes import make_node
from src.scenario import ALL_NODES, initial_position


def run(protocol: str, viz: bool) -> Dict[str, float]:
    METRICS.reset()
    LOCATIONS.clear()
    builder = SimulationBuilder(SimulationConfiguration(
        duration=SIMULATION_DURATION,
        real_time=viz,
        execution_logging=False,
    ))

    Node = make_node(protocol, viz)
    for node_id in ALL_NODES:  # a ordem de criação define os IDs (0 = torre)
        builder.add_node(Node, initial_position(node_id))

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler())
    builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=COMM_RANGE, delay=COMM_DELAY)))
    if viz:
        builder.add_handler(VisualizationHandler(VisualizationConfiguration(
            x_range=(-40.0, 90.0),
            y_range=(-65.0, 65.0),
            z_range=(0.0, 40.0),
            information_collection_interval=0.05,
            update_rate=0.05,
            open_browser=True,
        )))

    builder.build().start_simulation()
    return METRICS.summary()


COLUMNS = [
    ("Protocolo", "protocol", "{}"),                        # Tipo de protocolo usado
    ("Msg. Criadas", "created", "{}"),                      # Número de mensagens criadas
    ("Msg.Entregues", "delivered", "{}"),                   # Número de mensagens entregues (primeira chegada)
    ("PDR%", "pdr", "{:.1f}"),                              # Razão de mensagens entregues e criadas em % (PDR = delivered / created)
    ("Missão", "mission", "{}"),                            # Qtd de mensagens entregues dentro do tempo de missão (TTL)
    ("Lat. média(s)", "lat_mean", "{:.2f}"),                # Latência média de entrega (em segundos)
    ("Lat. mediana(s)", "lat_median", "{:.2f}"),            # Latência mediana de entrega (em segundos)
    ("Saltos médios", "hops_mean", "{:.2f}"),               # Número médio de saltos para entrega
    ("Num. Tx dados", "data_tx", "{}"),                     # Número de Dados transmitidos
    ("Num. Tx ctrl", "control_tx", "{}"),                   # Número de Mensagens de controle transmitidas
    ("Tx / entrega", "tx_per_delivery", "{:.2f}"),          # Razão entre transmissões e entregas
    ("Num. Rx. redund.", "redundant_receptions", "{}"),     # Número de Recepções redundantes
    ("Msg. Entregas dupl.", "duplicate_deliveries", "{}"),  # Número de Mensagens entregues duplicadas no nó de destino
    ("Msg. Desc. TTL", "ttl_drops", "{}"),                  # Número de Mensagens descartadas por expirar o TTL (limite de saltos)
    ("Podas zona", "zone_drops", "{}"),                     # Número de Mensagens descartadas por estarem fora da zona de encaminhamento
    ("Cópias expiradas (timeout)", "expired", "{}"),        # Número de Mensagens descartadas por expirar o tempo de vida (TTL) (timeoutent)
]


def print_table(results: List[Dict[str, float]]):
    """Imprime os resultados como tabela Markdown (pronta para o relatório)."""
    print("| " + " | ".join(title for title, _, _ in COLUMNS) + " |")
    print("|" + "|".join(" :---: " for _ in COLUMNS) + "|")
    for r in results:
        print("| " + " | ".join(fmt.format(r[key]) for _, key, fmt in COLUMNS) + " |")


def write_table_to_file(results: List[Dict[str, float]], filename: str):
    """Escreve os resultados como tabela Markdown em um arquivo."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(title for title, _, _ in COLUMNS) + " |\n")
        f.write("|" + "|".join(" :---: " for _ in COLUMNS) + "|\n")
        for r in results:
            f.write("| " + " | ".join(fmt.format(r[key]) for _, key, fmt in COLUMNS) + " |\n")
