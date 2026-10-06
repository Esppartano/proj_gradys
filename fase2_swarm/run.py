"""
Fase 2: Swarm Core em formação V (Torre + 9 Core + 4 satélites).

Código mantido como estava antes da refatoração da Fase 1 (ainda não usa a
base do template). Uso, a partir da raiz do projeto:
    python -m fase2_swarm.run            # com visualizador 3D
    python -m fase2_swarm.run --no-viz
"""
import argparse

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility.massless import MasslessMobilityConfiguration, MasslessMobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from fase2_swarm.base_protocol import METRICS
from fase2_swarm.swarmcore_protocol import SwarmCoreProtocol

NODE_POSITIONS = [
    (25.0, 0.0, 5.0),     # 0: Torre Terrestre Central
    (59.0, 0.0, 15.0),    # 1: Ápice Líder (C1)
    (61.0, -5.5, 15.0),   # 2: Asa Esquerda (C2)
    (63.0, -11.0, 15.0),  # 3: Asa Esquerda (C3)
    (65.0, -16.5, 15.0),  # 4: Asa Esquerda (C4 - Ronda)
    (67.0, -22.0, 15.0),  # 5: Ponta Esquerda (C5 - FF Control)
    (57.0, -5.5, 15.0),   # 6: Asa Direita (C6)
    (55.0, -11.0, 15.0),  # 7: Asa Direita (C7)
    (53.0, -16.5, 15.0),  # 8: Asa Direita (C8)
    (51.0, -22.0, 15.0),  # 9: Ponta Direita (C9 - Hub S3)
    (67.0, -22.0, 17.5),  # 10: S1 (tandem inicial com C5)
    (19.0, 47.6, 17.5),   # 11: S2
    (37.8, 46.2, 17.5),   # 12: S3
    (-19.9, 17.0, 17.5),  # 13: S4
]


def run_swarmcore(viz: bool) -> None:
    METRICS.reset()
    builder = SimulationBuilder(configuration=SimulationConfiguration(duration=35.0, real_time=viz))
    builder.add_handler(CommunicationHandler(communication_medium=CommunicationMedium(transmission_range=50.0, delay=0.01)))
    builder.add_handler(TimerHandler())
    builder.add_handler(MasslessMobilityHandler(MasslessMobilityConfiguration(default_speed=14.0)))
    if viz:
        builder.add_handler(VisualizationHandler(configuration=VisualizationConfiguration(
            information_collection_interval=0.05,
            update_rate=0.05,
            x_range=(-40.0, 105.0),
            y_range=(-75.0, 75.0),
            z_range=(0.0, 40.0),
            open_browser=True,
        )))
    for position in NODE_POSITIONS:
        builder.add_node(SwarmCoreProtocol, position)

    builder.build().start_simulation()
    METRICS.print_summary("Swarm Core (Formação V)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fase 2: Swarm Core em formação V")
    parser.add_argument("--no-viz", action="store_true")
    run_swarmcore(viz=not parser.parse_args().no_viz)
