"""
Estação base no solo: destino (sink) de todas as mensagens de roteamento.

Registra cada entrega em METRICS. No DTN, confirma a custódia dos bundles
recebidos e anuncia a própria posição com beacons.
"""
import json

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import (
    BroadcastMessageCommand,
    SendMessageCommand,
)
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.simulator.extension.visualization_controller import VisualizationController

from src.metrics import METRICS
from src.routing import messages as m
from utils.common.config import BASE_STATION_POS, BEACON_INTERVAL
from utils.viz_templates.constants import COLOR_START_POS


class BaseStationProtocol(IProtocol):

    send_beacons: bool = False

    def initialize(self) -> None:
        if self.send_beacons:
            self._schedule_beacon()

    def _schedule_beacon(self) -> None:
        self.provider.schedule_timer("beacon", self.provider.current_time() + BEACON_INTERVAL)

    def handle_timer(self, timer: str) -> None:
        if timer == "beacon":
            METRICS.control_tx += 1
            self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
                "msg_type": m.BEACON,
                "sender_id": self.provider.get_id(),
                "position": BASE_STATION_POS,
            })))
            self._schedule_beacon()

    def handle_packet(self, message: str) -> None:
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            return
        now = self.provider.current_time()
        kind = raw.get("msg_type")

        if kind == m.DATA:
            METRICS.record_delivery(raw, now)
        elif kind == m.BUNDLE:
            for msg in raw["messages"]:
                METRICS.record_delivery(msg, now)
            METRICS.control_tx += 1
            self.provider.send_communication_command(SendMessageCommand(json.dumps({
                "msg_type": m.ACK,
                "sender_id": self.provider.get_id(),
                "ids": [msg["message_id"] for msg in raw["messages"]],
            }), raw["sender_id"]))

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        pass

    def finish(self) -> None:
        pass


class BaseStationVizMixin:
    """Pinta a estação base de verde (mesma cor de BASE do template)."""

    def initialize(self) -> None:
        super().initialize()
        self._vc = VisualizationController(self)
        self.provider.schedule_timer("repaint", self.provider.current_time() + 1)

    def handle_timer(self, timer: str) -> None:
        super().handle_timer(timer)
        if timer == "repaint":
            self._vc.paint_node(self.provider.get_id(), COLOR_START_POS)
            self.provider.schedule_timer("repaint", self.provider.current_time() + 1)


def make_base_station(send_beacons: bool, viz: bool) -> type:
    bases = (BaseStationVizMixin, BaseStationProtocol) if viz else (BaseStationProtocol,)
    return type("BaseStation", bases, {"send_beacons": send_beacons})
