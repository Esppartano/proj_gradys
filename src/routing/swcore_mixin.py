"""
SwCore: roteamento pela árvore geradora do Swarm Core, com tabela de alcance.

Cada nó do Core conhece só os seus vizinhos na árvore (TREE_NEIGHBORS) e
mantém, para cada satélite, uma entrada com o nº do handshake:
  - "direct"   → AbleToDeliverDirectly (o satélite fez handshake comigo);
  - <vizinho>  → NextHop(Uy) na árvore;
  - None       → Unreachable.

- Handshake (camada de enlace): o hub marca "direct" e anuncia REACH(ep, seq)
  pela árvore; cada receptor faz table[ep] = remetente e repassa aos outros
  vizinhos da árvore (sem laços: é uma árvore).
- Despedida ou perda do satélite: o hub anuncia UNREACH(ep, seq). Anúncios
  com seq menor que o da entrada são descartados (velhos).
- Dados: o satélite entrega ao seu hub. No Core, nesta ordem:
    Direct (satélite ligado a mim)  → entrega direto;
    NextHop(Uy)                     → repassa pela árvore;
    Unreachable                     → guarda (entrega diferida, sem prazo:
                                      armazenamento ilimitado) até um REACH
                                      do destino.
- Satélites só trocam mensagens com o hub, enquanto acoplados (regra comum,
  em `RoutingMixin`): por isso a entrega a um satélite é sempre pelo estado
  Direct, no hub.
- O líder de mobilidade (C1) não tem papel especial na transmissão.
"""
from typing import Dict, Optional, Tuple, Union

from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import TREE_NEIGHBORS, label

DIRECT = "direct"
Route = Union[str, int, None]


class SwCoreMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self.table: Dict[int, Tuple[Route, int]] = {}  # satélite → (rota, seq)
        self._held: Dict[str, m.DataMessage] = {}      # id → mensagem guardada

    # ── Endpoints ─────────────────────────────────────────────────────────

    def _can_originate(self) -> bool:
        return self.role == "core" or self.hub is not None  # acumula enquanto longe do Core

    def _originate(self, message: m.DataMessage) -> None:
        self._seen.add(message["message_id"])
        if self.role == "core":  # nó do Core como origem: roteia ou guarda
            if not self._route(message):
                self._hold(message)
            return
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

    def _route(self, message: m.DataMessage) -> bool:
        """Tenta avançar a mensagem; retorna False se ela precisa esperar."""
        destination = message["destination"]
        route, _ = self.table.get(destination, (None, -1))
        if route == DIRECT and destination in self.tethered:
            self._send(message, destination)
            self._note("forwarded", f"Entregou {message['name']} direto a {label(destination)}", "forwarded")
        elif route not in (None, DIRECT):
            self._send(message, route)
            self._note("forwarded", f"Repassou {message['name']} a {label(route)}", "forwarded")
        else:
            return False
        return True

    def _hold(self, message: m.DataMessage) -> None:
        self._held[message["message_id"]] = message  # armazenamento ilimitado, sem prazo
        self._note("held", f"Guardou {message['name']} ({label(message['destination'])} inalcançável)")

    def _flush_held(self) -> None:
        for msg_id, msg in list(self._held.items()):
            if self._route(msg):
                del self._held[msg_id]

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
            self._hold(raw)
