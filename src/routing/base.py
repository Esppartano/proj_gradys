"""
Base comum dos mixins de roteamento.

Cada protocolo é um mixin colocado antes de `SwarmNode` (padrão de extensão
do template). O mixin:
  1. recebe da agenda de tráfego o pedido de envio (`_on_traffic`) e cria a
     mensagem de roteamento;
  2. trata as mensagens com `msg_type` de roteamento;
  3. mantém a tabela de vizinhos a partir de beacons (se o protocolo usar).
"""
import json
from typing import Dict, Optional, Tuple

from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand

from src.config import BEACON_INTERVAL, NEIGHBOR_TIMEOUT
from src.metrics import METRICS
from src.node import LOCATIONS
from src.routing import messages as m
from src.scenario import label

ROUTING_TYPES = {m.DATA, m.BUNDLE, m.ACK, m.BEACON}


class RoutingMixin:
    """Infraestrutura compartilhada; subclasses implementam `_originate` e `_on_routing`."""

    uses_beacons: bool = False

    def initialize(self) -> None:
        super().initialize()
        self._sequence = 0
        self._seen: set = set()
        self._neighbors: Dict[int, Tuple[m.Position, float]] = {}  # id → (posição, visto em)
        # Estado observável (lido pelo mixin de visualização; não afeta o protocolo)
        self.stats = {
            "created": 0, "received": 0, "forwarded": 0, "redundant": 0, "pruned": 0,
            "ttl_drops": 0, "handed_off": 0, "custody": 0, "expired": 0,
        }
        self.last_event: Optional[Tuple[str, str, float]] = None  # (tipo, texto, instante)
        if self.uses_beacons:
            self.provider.schedule_timer("beacon", self.provider.current_time() + BEACON_INTERVAL)

    # ── Hooks dos protocolos ──────────────────────────────────────────────

    def _originate(self, message: m.DataMessage) -> None:
        raise NotImplementedError

    def _on_routing(self, raw: dict) -> None:
        raise NotImplementedError

    def _on_beacon(self, sender: int) -> None:
        pass

    # ── Eventos (HUD, cores, log) ─────────────────────────────────────────

    def _note(self, kind: str, text: str, stat: Optional[str] = None, amount: int = 1) -> None:
        if stat:
            self.stats[stat] += amount
        self.last_event = (kind, text, self.provider.current_time())

    # ── Criação, envio e entrega ──────────────────────────────────────────

    def _on_traffic(self, destination: int, name: str) -> None:
        self._sequence += 1
        my_id = self.provider.get_id()
        message: m.DataMessage = {
            "msg_type": m.DATA,
            "message_id": f"{my_id}:{self._sequence}",
            "name": name,
            "origin_id": my_id,
            "destination": destination,
            "dest_pos": LOCATIONS.get(destination),
            "sender_id": my_id,
            "created_at": self.provider.current_time(),
            "hops": 1,
        }
        METRICS.created += 1
        self._note("created", f"Criou {name} para {label(destination)}", "created")
        self._originate(message)

    def _deliver(self, message: m.DataMessage) -> None:
        """Chegada ao destino final."""
        if METRICS.record_delivery(message, self.provider.current_time()):
            latency = self.provider.current_time() - message["created_at"]
            self._note(
                "delivered",
                f"Recebeu {message['name']} de {label(message['origin_id'])} "
                f"({message['hops']} saltos, {latency:.2f}s)",
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

    # ── Vizinhança ────────────────────────────────────────────────────────

    def _alive(self, peer_id: int) -> bool:
        """Vizinho ouvido há menos de NEIGHBOR_TIMEOUT (detecção real de enlace)."""
        entry = self._neighbors.get(peer_id)
        return entry is not None and self.provider.current_time() - entry[1] <= NEIGHBOR_TIMEOUT

    def _fresh_neighbors(self) -> Dict[int, m.Position]:
        return {peer: pos for peer, (pos, _) in self._neighbors.items() if self._alive(peer)}

    # ── Handlers do GrADySim ──────────────────────────────────────────────

    def handle_timer(self, timer: str) -> None:
        if timer == "beacon":
            self._broadcast({
                "msg_type": m.BEACON,
                "sender_id": self.provider.get_id(),
                "position": self._position,
            }, control=True)
            self.provider.schedule_timer("beacon", self.provider.current_time() + BEACON_INTERVAL)
            return
        super().handle_timer(timer)

    def handle_packet(self, message: str) -> None:
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            return
        kind = raw.get("msg_type")
        if kind == m.BEACON:
            self._neighbors[raw["sender_id"]] = (tuple(raw["position"]), self.provider.current_time())
            self._on_beacon(raw["sender_id"])
        elif kind in ROUTING_TYPES:
            self._on_routing(raw)
