"""
Base comum dos mixins de roteamento.

Cada protocolo é um mixin colocado antes da classe gerada por
`make_uav_protocol` (padrão de extensão do template). O mixin:
  1. intercepta a resposta dos sensores e gera uma mensagem de roteamento
     destinada à estação base, depois devolve a resposta ao template
     (que continua acumulando `self.packets`);
  2. trata as mensagens com `msg_type` de roteamento;
  3. repassa todo o resto ao template via super().
"""
import json
from typing import Optional

from gradysim.protocol.messages.communication import (
    BroadcastMessageCommand,
    SendMessageCommand,
)
from gradysim.protocol.messages.telemetry import Telemetry

from src.metrics import METRICS
from src.routing import messages as m
from utils.common.agent_types import AgentType

ROUTING_TYPES = {m.DATA, m.BUNDLE, m.ACK, m.BEACON}


class RoutingMixin:
    """Infraestrutura compartilhada; subclasses implementam `_originate` e `_on_routing`."""

    # Se True, a estação base anuncia sua posição com beacons (usado pelo DTN).
    needs_base_beacon: bool = False

    def initialize(self) -> None:
        super().initialize()
        self._sequence = 0
        self._seen: set = set()
        self._position: Optional[m.Position] = None

    # ── Hooks dos protocolos ──────────────────────────────────────────────

    def _originate(self, message: m.DataMessage) -> None:
        raise NotImplementedError

    def _on_routing(self, raw: dict) -> None:
        raise NotImplementedError

    # ── Criação e envio ───────────────────────────────────────────────────

    def _new_message(self, payload: dict) -> m.DataMessage:
        self._sequence += 1
        my_id = self.provider.get_id()
        METRICS.created += 1
        return {
            "msg_type": m.DATA,
            "message_id": f"{my_id}:{self._sequence}",
            "origin_id": my_id,
            "sender_id": my_id,
            "created_at": self.provider.current_time(),
            "hops": 1,
            "payload": dict(payload),
        }

    def _broadcast(self, message: dict, control: bool = False) -> None:
        self._count_tx(control)
        self.provider.send_communication_command(BroadcastMessageCommand(json.dumps(message)))

    def _unicast(self, message: dict, destination: int, control: bool = False) -> None:
        self._count_tx(control)
        self.provider.send_communication_command(SendMessageCommand(json.dumps(message), destination))

    @staticmethod
    def _count_tx(control: bool) -> None:
        if control:
            METRICS.control_tx += 1
        else:
            METRICS.data_tx += 1

    # ── Handlers do GrADySim ──────────────────────────────────────────────

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        self._position = tuple(telemetry.current_position)
        super().handle_telemetry(telemetry)

    def handle_packet(self, message: str) -> None:
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            return super().handle_packet(message)

        if raw.get("msg_type") in ROUTING_TYPES:
            self._on_routing(raw)
            return

        super().handle_packet(message)
        if raw.get("sender_type") == AgentType.SENSOR.value and raw.get("packets"):
            self._originate(self._new_message(raw["packets"]))
