"""
Base comum dos mixins de roteamento.

Cada protocolo é um mixin colocado antes de `SwarmNode`. O mixin:
  1. recebe da agenda de tráfego o pedido de envio (`_on_traffic`) e cria a
     mensagem; a origem acumula as mensagens enquanto está isolada
     (`_can_originate`) e as libera ao ganhar contato;
  2. trata os pacotes de roteamento (`_on_routing`);
  3. conta transmissões e recepções para as métricas.
"""
import json
from typing import List, Optional, Tuple

from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand

from src.metrics import METRICS
from src.routing import messages as m


class RoutingMixin:
    """Infraestrutura compartilhada; subclasses implementam `_originate` e `_on_routing`."""

    def initialize(self) -> None:
        super().initialize()
        self._sequence = 0
        self._seen: set = set()
        self._outbox: List[m.DataMessage] = []  # criadas enquanto isolado
        # Estado observável (lido pela visualização; não afeta o protocolo)
        self.stats = {
            "created": 0, "received": 0, "forwarded": 0, "redundant": 0, "pruned": 0,
            "ttl_drops": 0, "handed_off": 0, "custody": 0, "expired": 0,
        }
        self.last_event: Optional[Tuple[str, str, float]] = None  # (tipo, texto, instante)

    # ── Hooks dos protocolos ──────────────────────────────────────────────

    def _originate(self, message: m.DataMessage) -> None:
        raise NotImplementedError

    def _on_routing(self, raw: dict) -> None:
        raise NotImplementedError

    def _can_originate(self) -> bool:
        """A origem só transmite com algum vizinho ao alcance."""
        return bool(self.neighbors())

    # ── Eventos (HUD, cores, log) ─────────────────────────────────────────

    def _note(self, kind: str, text: str, stat: Optional[str] = None, amount: int = 1) -> None:
        if stat:
            self.stats[stat] += amount
        self.last_event = (kind, text, self.provider.current_time())
        self._log(text)

    # ── Criação, envio e entrega ──────────────────────────────────────────

    def _on_traffic(self, destination: int, name: str) -> None:
        self._sequence += 1
        message: m.DataMessage = {
            "msg_type": m.DATA,
            "message_id": f"{self.node_id}:{self._sequence}",
            "name": name,
            "origin_id": self.node_id,
            "destination": destination,
            "sender_id": self.node_id,
            "created_at": self.provider.current_time(),
            "hops": 0,
        }
        METRICS.created += 1
        self._note("created", f"Criou {name}", "created")
        self._outbox.append(message)
        self._flush_outbox()

    def _flush_outbox(self) -> None:
        if not self._outbox or not self._can_originate():
            return
        outbox, self._outbox = self._outbox, []
        for message in outbox:
            self._originate(message)

    def _on_contact(self, peer: int) -> None:
        super()._on_contact(peer)
        self._flush_outbox()

    def _on_hub(self, hub) -> None:
        super()._on_hub(hub)
        self._flush_outbox()

    def _deliver(self, message: m.DataMessage) -> None:
        """Chegada ao destino final."""
        now = self.provider.current_time()
        if METRICS.record_delivery(message, now):
            self._note(
                "delivered",
                f"Recebeu {message['name']} ({message['hops']} saltos, {now - message['created_at']:.2f}s)",
                "received",
            )

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

    def _redundant(self) -> None:
        METRICS.redundant_receptions += 1
        self.stats["redundant"] += 1

    def _forward_copy(self, message: m.DataMessage, **changes) -> dict:
        """Cópia da mensagem para retransmitir: +1 salto, eu como remetente."""
        return {**message, "hops": message["hops"] + 1, "sender_id": self.node_id, **changes}

    # ── Recepção ──────────────────────────────────────────────────────────

    def _on_packet(self, raw: dict) -> None:
        if raw.get("msg_type") in m.ROUTING_TYPES:
            METRICS.rx += 1
            self._on_routing(raw)

