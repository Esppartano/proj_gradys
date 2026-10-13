from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler, VisualizationConfiguration
from protocolo import Protocolo


def main():
    duration = 60
    simulation_config = SimulationConfiguration(duration=duration, real_time=True)
    simulation_builder = SimulationBuilder(simulation_config)
    simulation_builder.add_node(Protocolo, position=(0, 0, 10))
    simulation_builder.add_handler(TimerHandler())
    visualization_config = VisualizationConfiguration(open_browser=True)
    simulation_builder.add_handler(VisualizationHandler(visualization_config))
    simulation = simulation_builder.build()
    simulation.start_simulation()


if __name__ == "__main__":
    main()
