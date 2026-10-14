"""
Motor: monta e roda a simulação de um único cenário (Swarm Core em V);
só o protocolo muda. O ponto de entrada é o menu em `main.py`, na raiz.
"""
from typing import Dict, List

from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityConfiguration, MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.config import COMM_DELAY, COMM_RANGE, MOBILITY_UPDATE, SIMULATION_DURATION
from src import eventlog
from src.metrics import METRICS
from src.nodes import make_node
from src.radio import SwarmCommunicationHandler
from src.scenario import ALL_NODES, initial_position


def run(protocol: str, viz: bool) -> Dict[str, float]:
    """Roda um cenário e grava o log de eventos em logs/<protocolo>.log."""
    METRICS.reset()
    log_path = eventlog.open_log(
        protocol, f"# Protocolo: {protocol} | modo: {'visualizador 3D' if viz else 'headless'}"
                  f" | duração: {SIMULATION_DURATION:.0f}s")
    print(f"\n>>> Log de eventos sendo gravado em: {log_path}\n")
    builder = SimulationBuilder(SimulationConfiguration(
        duration=SIMULATION_DURATION,
        real_time=viz,
        execution_logging=False,
    ))

    Node = make_node(protocol, viz)
    for node_id in ALL_NODES:  # a ordem de criação define os IDs (0 = BS)
        builder.add_node(Node, initial_position(node_id))

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler(MobilityConfiguration(update_rate=MOBILITY_UPDATE)))
    builder.add_handler(SwarmCommunicationHandler(CommunicationMedium(transmission_range=COMM_RANGE, delay=COMM_DELAY)))
    if viz:
        builder.add_handler(VisualizationHandler(VisualizationConfiguration(
            x_range=(-50.0, 50.0),
            y_range=(-50.0, 50.0),
            z_range=(0.0, 20.0),
            information_collection_interval=0.1,
            update_rate=0.1,
            open_browser=True,
        )))

    try:
        builder.build().start_simulation()
    finally:
        summary = METRICS.summary()
        eventlog.close_log(_table([{"protocol": protocol, **summary}]))
    print(f"\n>>> Log de eventos salvo em: {log_path}\n")
    return summary


COLUMNS = [
    ("Protocolo", "protocol", "{}"),
    ("Criadas", "created", "{}"),
    ("Entregues", "delivered", "{}"),
    ("PDR%", "pdr", "{:.1f}"),
    ("Lat. média(s)", "lat_mean", "{:.2f}"),
    ("Lat. mediana(s)", "lat_median", "{:.2f}"),
    ("Saltos médios", "hops_mean", "{:.2f}"),
    ("Tx dados", "data_tx", "{}"),
    ("Msgs dados tx", "data_msgs_tx", "{}"),
    ("Tx controle", "control_tx", "{}"),
    ("Tx / entrega", "tx_per_delivery", "{:.2f}"),
    ("Rx redund.", "redundant_receptions", "{}"),
    ("Entregas dupl.", "duplicate_deliveries", "{}"),
    ("Desc. TTL", "ttl_drops", "{}"),
    ("Podas zona", "zone_drops", "{}"),
    ("Expiradas", "expired", "{}"),
    ("Energia", "energy", "{:.0f}"),
]


def _table(results: List[Dict[str, float]]) -> str:
    lines = ["| " + " | ".join(title for title, _, _ in COLUMNS) + " |",
             "|" + "|".join(" :---: " for _ in COLUMNS) + "|"]
    for r in results:
        lines.append("| " + " | ".join(fmt.format(r[key]) for _, key, fmt in COLUMNS) + " |")
    return "\n".join(lines)


def print_table(results: List[Dict[str, float]]):
    """Imprime os resultados como tabela Markdown (pronta para o relatório)."""
    print(_table(results))


def write_table_to_file(results: List[Dict[str, float]], filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(_table(results) + "\n")
