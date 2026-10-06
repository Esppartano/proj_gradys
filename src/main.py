"""
Ponto de entrada da simulação (Fase 1: comparação de roteamento).

Um único cenário (sensores + 12 UAVs em patrulha + estação base); só o
protocolo de roteamento muda.

Uso (sempre a partir da raiz do projeto):
    python -m src.main --protocol dtn            # com visualizador 3D
    python -m src.main --protocol geocast --no-viz
    python -m src.main --benchmark               # roda os 3 protocolos headless
"""
import argparse
import logging
from math import dist
from typing import Dict, List

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.base_station import make_base_station
from src.metrics import METRICS
from src.sensor import Sensor
from src.uav import PROTOCOLS, make_uav
from utils.actor_templates.sensor_template import SensorProtocol
from utils.common.config import (
    BASE_GROUND,
    COMM_DELAY,
    COMM_RANGE,
    ENDPOINT_GROUND,
    FLIGHT_ALT,
    LEFT_WAYPOINTS,
    NUM_UAVS,
    RIGHT_WAYPOINTS,
    SENSOR_POSITIONS,
    SIMULATION_DURATION,
    UAV_SPEED,
)


def _patrol_cycle(waypoints) -> float:
    """Tempo de ida e volta pela rota, em segundos."""
    length = sum(dist(a[:2], b[:2]) for a, b in zip(waypoints, waypoints[1:]))
    return 2 * length / UAV_SPEED


def run(protocol: str, viz: bool) -> Dict[str, float]:
    METRICS.reset()
    builder = SimulationBuilder(SimulationConfiguration(
        duration=SIMULATION_DURATION,
        real_time=viz,
        execution_logging=False,
    ))

    # Nó 0: estação base. Os sensores vêm em seguida porque o template deriva
    # o nome do sensor do ID (sensor_N tem ID N+1).
    builder.add_node(make_base_station(PROTOCOLS[protocol].needs_base_beacon, viz), BASE_GROUND)
    for sensor_pos in SENSOR_POSITIONS.values():
        builder.add_node(Sensor if viz else SensorProtocol, sensor_pos)

    # Metade dos UAVs em cada rota do template em torno do obstáculo, com
    # decolagens escalonadas por 1/per_route do ciclo para espalhá-los na rota.
    per_route = NUM_UAVS // 2
    for waypoints in (LEFT_WAYPOINTS, RIGHT_WAYPOINTS):
        step = _patrol_cycle(waypoints) / per_route
        for i in range(per_route):
            builder.add_node(make_uav(protocol, waypoints, i * step, viz), BASE_GROUND)

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler())
    builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=COMM_RANGE, delay=COMM_DELAY)))
    if viz:
        padding = 50
        all_x = [p[0] for p in SENSOR_POSITIONS.values()] + [BASE_GROUND[0], ENDPOINT_GROUND[0]]
        all_y = [p[1] for p in SENSOR_POSITIONS.values()] + [BASE_GROUND[1], ENDPOINT_GROUND[1]]
        builder.add_handler(VisualizationHandler(VisualizationConfiguration(
            x_range=(min(all_x) - padding, max(all_x) + padding),
            y_range=(min(all_y) - padding, max(all_y) + padding),
            z_range=(0, FLIGHT_ALT + 20),
            open_browser=True,
        )))

    builder.build().start_simulation()
    return METRICS.summary()


COLUMNS = [
    ("Protocolo", "protocol", "{}"),
    ("Criadas", "created", "{}"),
    ("Entregues", "delivered", "{}"),
    ("PDR %", "pdr", "{:.1f}"),
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
    ("Desc. buffer", "buffer_drops", "{}"),
]


def print_table(results: List[Dict[str, float]]) -> None:
    """Imprime os resultados como tabela Markdown (pronta para o relatório)."""
    print("| " + " | ".join(title for title, _, _ in COLUMNS) + " |")
    print("|" + "|".join(" :---: " for _ in COLUMNS) + "|")
    for r in results:
        print("| " + " | ".join(fmt.format(r[key]) for _, key, fmt in COLUMNS) + " |")


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparação de roteamento em FANET (GrADySim)")
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="flooding")
    parser.add_argument("--no-viz", action="store_true", help="desativa o visualizador 3D")
    parser.add_argument("--benchmark", action="store_true", help="roda todos os protocolos headless")
    args = parser.parse_args()
    # Os logs INFO do template (uma linha por coleta de sensor) e do GrADySim
    # poluem a saída; avisos e erros continuam visíveis.
    logging.disable(logging.INFO)

    protocols = list(PROTOCOLS) if args.benchmark else [args.protocol]
    viz = not (args.no_viz or args.benchmark)
    results = [{"protocol": p, **run(p, viz)} for p in protocols]
    print_table(results)


if __name__ == "__main__":
    main()
