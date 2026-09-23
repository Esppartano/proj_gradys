from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import Position, squared_distance
from gradysim.simulator.extension.visualization_controller import VisualizationController
from messages import Packet, PacketType


@dataclass
class SimulationMetrics:
    total_transmissions: int = 0
    total_broadcasts: int = 0
    total_unicasts: int = 0
    data_sent: int = 0
    data_delivered: int = 0
    ack_sent: int = 0
    ack_delivered: int = 0
    delivery_latency: Optional[float] = None
    round_trip_time: Optional[float] = None
    hops: int = 0
    mission_success: bool = False
    events: List[Dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.total_transmissions = 0
        self.total_broadcasts = 0
        self.total_unicasts = 0
        self.data_sent = 0
        self.data_delivered = 0
        self.ack_sent = 0
        self.ack_delivered = 0
        self.delivery_latency = None
        self.round_trip_time = None
        self.hops = 0
        self.mission_success = False
        self.events.clear()

    def record_transmission(self, is_broadcast: bool = True) -> None:
        self.total_transmissions += 1
        if is_broadcast:
            self.total_broadcasts += 1
        else:
            self.total_unicasts += 1

    def print_summary(self, scenario_name: str) -> None:
        pdr = (self.data_delivered / self.data_sent * 100.0) if self.data_sent > 0 else 0.0
        print("\n" + "=" * 65)
        print(f"   RELATÓRIO DE MÉTRICAS: {scenario_name.upper()}")
        print("=" * 65)
        print(f"  • Status da Missão:        {'CONCLUÍDA COM SUCESSO' if self.mission_success else 'NÃO CONCLUÍDA'}")
        print(f"  • Taxa de Entrega (PDR):   {pdr:.1f}% ({self.data_delivered}/{self.data_sent})")
        lat_str = f"{self.delivery_latency:.2f} s" if self.delivery_latency is not None else "N/A"
        print(f"  • Latência de Entrega:     {lat_str}")
        rtt_str = f"{self.round_trip_time:.2f} s" if self.round_trip_time is not None else "N/A"
        print(f"  • RTT (Round Trip Time):   {rtt_str}")
        print(f"  • Saltos Percorridos:      {self.hops}")
        print(f"  • Total Transmissões Rádio:{self.total_transmissions} (Broadcasts: {self.total_broadcasts}, Unicasts: {self.total_unicasts})")
        print("=" * 65 + "\n")


METRICS = SimulationMetrics()


class BaseFANETProtocol(IProtocol):
    """
    Protocolo base abstrato para redes FANET/DTN aderente ao GrADyS-SIM NG.
    Encapsula o uso das classes oficiais de comando, telemetria, visualização 3D e métricas.
    """

    def __init__(self):
        self.current_pos: Position = (0.0, 0.0, 0.0)
        self.buffer: List[Packet] = []
        self.seen_packets: Set[str] = set()
        self.mission_completed: bool = False
        self.current_target: Optional[Position] = None
        self._vis_controller: Optional[VisualizationController] = None
        self._current_color: Tuple[int, int, int] = (180, 180, 180)
        self._last_vis_sync: float = -1.0

    def initialize(self) -> None:
        pass

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        self.current_pos = telemetry.current_position
        try:
            now = self.provider.current_time()
            if now - self._last_vis_sync >= 0.5:
                self._last_vis_sync = now
                self.vis.paint_node(self.provider.get_id(), self._current_color)
                self.vis.show_node_id(self.provider.get_id(), True)
                if self.provider.get_id() == 0:
                    self.vis.resize_nodes(2.5)
        except Exception:
            pass

    def handle_timer(self, timer: str) -> None:
        pass

    def handle_packet(self, message: str) -> None:
        pass

    def finish(self) -> None:
        pass

    # -----------------------------------------------------------------
    # Visualização e Variáveis Rastreadas (GrADyS-SIM Web Visualizer)
    # -----------------------------------------------------------------
    @property
    def vis(self) -> VisualizationController:
        if self._vis_controller is None:
            self._vis_controller = VisualizationController(self)
        return self._vis_controller

    def set_node_color(self, color: Tuple[Any, Any, Any]) -> None:
        """
        Define a cor RGB do nó na interface 3D web.
        Converte automaticamente valores normalizados (0.0 - 1.0) para inteiros CSS (0 - 255).
        Armazena a cor ativa para sincronização periódica contínua via telemetria.
        """
        try:
            r, g, b = color
            if max(r, g, b) <= 1.0:
                r, g, b = int(r * 255), int(g * 255), int(b * 255)
            else:
                r, g, b = int(r), int(g), int(b)
            self._current_color = (r, g, b)
            self.vis.paint_node(self.provider.get_id(), (r, g, b))
        except Exception:
            pass

    def resize_all_nodes(self, size: float = 2.5) -> None:
        """Aumenta o tamanho das esferas dos nós no visualizador 3D para destacá-los."""
        try:
            self.vis.resize_nodes(size)
        except Exception:
            pass

    def show_node_id(self, show: bool = True) -> None:
        """Exibe a etiqueta com o ID flutuando sobre o drone na interface 3D."""
        try:
            self.vis.show_node_id(self.provider.get_id(), show)
        except Exception:
            pass

    def set_tracked_variable(self, key: str, value: Any) -> None:
        """Exibe variáveis no painel de telemetria lateral ao inspecionar o nó."""
        if hasattr(self, "provider") and hasattr(self.provider, "tracked_variables"):
            self.provider.tracked_variables[key] = value

    # -----------------------------------------------------------------
    # Comandos Oficiais de Comunicação (GrADyS-SIM NG)
    # -----------------------------------------------------------------
    def send_broadcast(self, message: str) -> None:
        METRICS.record_transmission(is_broadcast=True)
        command = BroadcastMessageCommand(message)
        self.provider.send_communication_command(command)

    def send_unicast(self, message: str, destination: int) -> None:
        METRICS.record_transmission(is_broadcast=False)
        command = SendMessageCommand(message, destination)
        self.provider.send_communication_command(command)

    # -----------------------------------------------------------------
    # Comandos Oficiais de Mobilidade (GrADyS-SIM NG)
    # -----------------------------------------------------------------
    def fly_to(self, x: float, y: float, z: float) -> None:
        self.current_target = (x, y, z)
        command = GotoCoordsMobilityCommand(x, y, z)
        self.provider.send_mobility_command(command)

    def set_speed(self, speed: float) -> None:
        command = SetSpeedMobilityCommand(speed)
        self.provider.send_mobility_command(command)

    # -----------------------------------------------------------------
    # Auxiliares de Navegação e Registro
    # -----------------------------------------------------------------
    def has_reached(self, target: Position, tolerance: float = 2.0) -> bool:
        return squared_distance(self.current_pos, target) <= (tolerance ** 2)

    def log(self, message: str) -> None:
        now = self.provider.current_time()
        node_id = self.provider.get_id()
        print(f"[{now:5.1f}s][Nó {node_id}] {message}")
