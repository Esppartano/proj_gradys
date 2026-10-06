"""
Orquestração: um único cenário (Swarm Core em V), só o protocolo muda.

O menu interativo fica em `main.py`, na raiz. Uso direto:
    python -m src.main --protocol tree            # visualizador 3D
    python -m src.main --protocol dtn --no-viz
    python -m src.main --benchmark                # os 4 protocolos headless
"""
import argparse
import logging
from typing import Dict, List

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.config import COMM_DELAY, COMM_RANGE, SIMULATION_DURATION
from src.metrics import METRICS
from src.node import LOCATIONS
from src.nodes import PROTOCOLS, make_node
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
    ("Protocolo", "protocol", "{}"),
    ("Criadas", "created", "{}"),
    ("Entregues", "delivered", "{}"),
    ("PDR %", "pdr", "{:.1f}"),
    ("Missão", "mission", "{}"),
    ("Lat. média s", "lat_mean", "{:.2f}"),
    ("Lat. mediana s", "lat_median", "{:.2f}"),
    ("Saltos médios", "hops_mean", "{:.2f}"),
    ("Tx dados", "data_tx", "{}"),
    ("Tx controle", "control_tx", "{}"),
    ("Tx / entrega", "tx_per_delivery", "{:.2f}"),
    ("Recep. redund.", "redundant_receptions", "{}"),
    ("Entregas dupl.", "duplicate_deliveries", "{}"),
    ("Desc. TTL", "ttl_drops", "{}"),
    ("Podas zona", "zone_drops", "{}"),
    ("Cópias expiradas", "expired", "{}"),
]


def print_table(results: List[Dict[str, float]]) -> None:
    """Imprime os resultados como tabela Markdown (pronta para o relatório)."""
    print("| " + " | ".join(title for title, _, _ in COLUMNS) + " |")
    print("|" + "|".join(" :---: " for _ in COLUMNS) + "|")
    for r in results:
        print("| " + " | ".join(fmt.format(r[key]) for _, key, fmt in COLUMNS) + " |")


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparação de roteamento no Swarm Core (GrADySim)")
    parser.add_argument("--protocol", choices=list(PROTOCOLS), default="tree")
    parser.add_argument("--no-viz", action="store_true", help="desativa o visualizador 3D")
    parser.add_argument("--benchmark", action="store_true", help="roda todos os protocolos headless")
    args = parser.parse_args()
    logging.disable(logging.INFO)

    protocols = list(PROTOCOLS) if args.benchmark else [args.protocol]
    viz = not (args.no_viz or args.benchmark)
    print_table([{"protocol": p, **run(p, viz)} for p in protocols])


if __name__ == "__main__":
    main()
