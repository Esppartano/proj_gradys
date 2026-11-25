"""
Sensores do cenário do T2 (nós estáticos ao longo dos eixos dos satélites).

Enunciado: "Os sensores [...] devem ter identificadores únicos, ímpares ou pares.
Se o satélite encontrar um sensor par, deve publicar no tópico T2; inversamente, se
encontrar um sensor ímpar, deve publicar no tópico T1." Como no repositório do
professor (routing-ricardo), os sensores ficam numa cruz ao longo dos eixos e o
satélite coleta as leituras ao passar; o layout e o protocolo aqui são próprios.

Cada sensor gera uma leitura a cada SENSOR_READING_INTERVAL s e as guarda. Ao ouvir
o beacon de enlace de um satélite (que todo nó emite a cada 0,2 s), entrega as
leituras guardadas a ele (`sensor_data`) e esvazia o buffer. Não fala com o Core.
"""
import json

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import SendMessageCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.config import SENSOR_READING_INTERVAL
from src.metrics import METRICS
from src.scenario import label

MSG_SENSOR_DATA = "sensor_data"
READING_TIMER = "reading"


class SensorNode(IProtocol):

    def initialize(self) -> None:
        self.node_id = self.provider.get_id()
        self.readings = 1        # leituras guardadas, ainda não coletadas (já começa com uma)
        self.collected = 0       # leituras entregues a satélites (só para o HUD)
        METRICS.register_node(self.node_id)  # aparece na tabela de energia mesmo sem tráfego
        self.provider.schedule_timer(READING_TIMER, SENSOR_READING_INTERVAL)

    def handle_timer(self, timer: str) -> None:
        if timer == READING_TIMER:
            self.readings += 1
            self.provider.schedule_timer(READING_TIMER, self.provider.current_time() + SENSOR_READING_INTERVAL)

    def handle_packet(self, message: str) -> None:
        METRICS.count_rx(self.node_id, message)  # energia por nó: o rádio ouve tudo ao alcance
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            return
        if raw.get("msg_type") != "link" or raw.get("role") != "satellite" or not self.readings:
            return
        message = json.dumps({"msg_type": MSG_SENSOR_DATA, "sender_id": self.node_id, "readings": self.readings})
        self.provider.send_communication_command(SendMessageCommand(message, raw["id"]))
        METRICS.count_tx(self.node_id, message)
        self.collected += self.readings
        self.readings = 0
        self._on_collected()

    def _on_collected(self) -> None:
        """Gancho (visualização)."""

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        pass


COLOR_EVEN = (0, 160, 255)   # azul: sensor par (satélite publica em T2)
COLOR_ODD = (120, 200, 0)    # verde-oliva: sensor ímpar (satélite publica em T1)


class SensorVizMixin:
    """Modo 3D: cor pela paridade e leituras no HUD."""

    def initialize(self) -> None:
        super().initialize()
        from gradysim.simulator.extension.visualization_controller import VisualizationController
        self._vc = VisualizationController(self)
        self._paint()

    def handle_timer(self, timer: str) -> None:
        super().handle_timer(timer)
        self._paint()

    def _on_collected(self) -> None:
        super()._on_collected()
        self._paint()

    def _paint(self) -> None:
        self._vc.paint_node(self.node_id, COLOR_EVEN if self.node_id % 2 == 0 else COLOR_ODD)
        self._vc.show_node_id(self.node_id, True)
        hud = self.provider.tracked_variables
        hud["Nó"] = label(self.node_id)
        hud["Tópico"] = "T2 (par)" if self.node_id % 2 == 0 else "T1 (ímpar)"
        hud["Leituras guardadas / coletadas"] = f"{self.readings} / {self.collected}"


def make_sensor(viz: bool) -> type:
    return type("SensorViz", (SensorVizMixin, SensorNode), {}) if viz else SensorNode
