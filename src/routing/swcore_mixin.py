"""
SwCore: roteamento pela árvore geradora do Swarm Core, com tabela de alcance.

Cada nó do Core conhece só os seus vizinhos na árvore (TREE_NEIGHBORS) e
mantém, para cada endpoint (satélite ou BS), uma entrada com o nº do handshake:
  - "direct"   → AbleToDeliverDirectly (o endpoint fez handshake comigo);
  - <vizinho>  → NextHop(Uy) na árvore;
  - None       → Unreachable.

- Handshake (camada de enlace): o hub marca "direct" e anuncia REACH(ep, seq)
  pela árvore; cada receptor faz table[ep] = remetente e repassa aos outros
  vizinhos da árvore (sem laços: é uma árvore).
- Despedida ou perda do endpoint: o hub anuncia UNREACH(ep, seq). Anúncios
  com seq menor que o da entrada são descartados (velhos).
- Dados: o endpoint entrega ao seu hub. No Core: se ouve o destino (hub ou
  backup que o sente), entrega direto; se há próximo salto, repassa; se está
  Unreachable, guarda (entrega diferida) até um REACH ou contato com o destino.
- O líder de mobilidade (C1) não tem papel especial na transmissão.
"""
from typing import Dict, Optional, Tuple, Union

from src.config import LINK_BEACON, SWCORE_HOLD_TIME
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import TREE_NEIGHBORS, label

DIRECT = "direct"
Route = Union[str, int, None]


class SwCoreMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self.table: Dict[int, Tuple[Route, int]] = {}             # endpoint → (rota, seq)
        self._held: Dict[str, Tuple[m.DataMessage, float]] = {}   # id → (msg, expira em)

    # ── Endpoints ─────────────────────────────────────────────────────────

    def _can_originate(self) -> bool:
        return self.role == "core" or self.hub is not None  # acumula enquanto longe do Core

    def _originate(self, message: m.DataMessage) -> None:
        self._seen.add(message["message_id"])
        self._send(message, self.hub)
        self._note("forwarded", f"Entregou {message['name']} ao hub {label(self.hub)}", "forwarded")

    # ── Tabela de alcance ─────────────────────────────────────────────────

    def _announce(self, kind: str, endpoint: int, seq: int, exclude: Optional[int] = None) -> None:
        for peer in TREE_NEIGHBORS[self.node_id]:
            if peer != exclude:
                self._unicast({"msg_type": kind, "sender_id": self.node_id, "endpoint": endpoint, "seq": seq},
                              peer, control=True)

    def _on_link_up(self, endpoint: int, seq: int) -> None:
        super()._on_link_up(endpoint, seq)
        self.table[endpoint] = (DIRECT, seq)
        self._announce(m.REACH, endpoint, seq)
        self._note("reach", f"{label(endpoint)} conectou: anunciou alcance")
        self._flush_held()

    def _on_link_down(self, endpoint: int, seq: int) -> None:
        super()._on_link_down(endpoint, seq)
        route, current = self.table.get(endpoint, (None, -1))
        if route == DIRECT and current == seq:
            self.table[endpoint] = (None, seq)
            self._announce(m.UNREACH, endpoint, seq)
            self._note("unreach", f"{label(endpoint)} desconectou: anunciou perda")

    def _on_announce(self, raw: dict) -> None:
        endpoint, seq, sender = raw["endpoint"], raw["seq"], raw["sender_id"]
        _, current = self.table.get(endpoint, (None, -1))
        if raw["msg_type"] == m.REACH and seq > current:
            self.table[endpoint] = (sender, seq)
        elif raw["msg_type"] == m.UNREACH and seq >= current:
            self.table[endpoint] = (None, seq)
        else:
            return  # anúncio velho: não repassa
        self._announce(raw["msg_type"], endpoint, seq, exclude=sender)
        self._flush_held()

    # ── Encaminhamento ────────────────────────────────────────────────────

    def _send(self, message: m.DataMessage, peer: int) -> None:
        self._unicast(self._forward_copy(message), peer)

    def _hears_directly(self, endpoint: int) -> bool:
        """Hub do endpoint, ou backup que o ouviu há menos de um período de beacon."""
        if endpoint in self.tethered:
            return True
        link = self._links.get(endpoint)
        limit = 1.2 * LINK_BEACON[link.role] if link else 0
        return link is not None and self.provider.current_time() - link.heard_at <= limit

    def _route(self, message: m.DataMessage) -> bool:
        """Tenta avançar a mensagem; retorna False se ela precisa esperar."""
        destination = message["destination"]
        if self._hears_directly(destination):
            self._send(message, destination)
            self._note("forwarded", f"Entregou {message['name']} direto a {label(destination)}", "forwarded")
            return True
        route, _ = self.table.get(destination, (None, -1))
        if route is None or route == DIRECT:
            return False
        self._send(message, route)
        self._note("forwarded", f"Repassou {message['name']} a {label(route)}", "forwarded")
        return True

    def _flush_held(self) -> None:
        now = self.provider.current_time()
        for msg_id, (msg, expires) in list(self._held.items()):
            if now > expires:
                del self._held[msg_id]
                METRICS.expired += 1
                self.stats["expired"] += 1
            elif self._route(msg):
                del self._held[msg_id]

    def _on_contact(self, peer: int) -> None:
        super()._on_contact(peer)
        if self.role == "core":
            self._flush_held()

    def _on_routing(self, raw: dict) -> None:
        kind = raw["msg_type"]
        if kind in (m.REACH, m.UNREACH):
            self._on_announce(raw)
            return
        if kind != m.DATA:
            return
        if raw["destination"] == self.node_id:
            self._deliver(raw)
            return
        if raw["message_id"] in self._seen:
            self._redundant()
            return
        self._seen.add(raw["message_id"])
        if self.role == "core" and not self._route(raw):
            self._held[raw["message_id"]] = (raw, self.provider.current_time() + SWCORE_HOLD_TIME)
            self._note("held", f"Guardou {raw['name']} ({label(raw['destination'])} inalcançável)")
