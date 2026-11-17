"""
SwCore: roteamento pela árvore geradora do Swarm Core, com tabela de alcance.

Cada nó do Core conhece só os seus vizinhos na árvore (TREE_NEIGHBORS) e
mantém uma tabela com os outros 8 nós do Core e os satélites. Para cada
satélite, a entrada guarda o nº do handshake:
  - "direct"   → AbleToDeliverDirectly (o satélite fez handshake comigo);
  - <vizinho>  → NextHop(Uy) na árvore;
  - None       → Unreachable.

- Handshake (camada de enlace): o hub marca "direct" e anuncia REACH(ep, seq)
  pela árvore; cada receptor faz table[ep] = remetente e repassa aos outros
  vizinhos da árvore (sem laços: é uma árvore).
- Nós do Core: ao (voltar a) ouvir um vizinho da árvore, o nó lhe manda um
  SYNC com a própria entrada (REACH de si mesmo, seq 0) e toda a tabela, menos
  o que aprendeu desse vizinho. Cada entrada é tratada como um anúncio e se
  espalha pela árvore: assim cada nó aprende o próximo salto para os outros 8
  e recupera anúncios perdidos enquanto um vizinho estava em falha. A rota
  para um nó do Core não muda (a árvore é fixa), então seq 0 basta.
- Despedida ou perda do satélite: o hub anuncia UNREACH(ep, seq). Anúncios
  com seq menor que o da entrada são descartados (velhos).
- Dados: o satélite entrega ao seu hub. No Core, nesta ordem:
    Direct (satélite ligado a mim)  → entrega direto;
    NextHop(Uy)                     → repassa pela árvore;
    Unreachable                     → guarda (entrega diferida, sem prazo:
                                      armazenamento ilimitado) até um REACH
                                      do destino.
- Confirmação salto a salto: quem recebe um dado responde HOP_ACK a quem o
  enviou; sem HOP_ACK em SW_HOP_ACK_TIMEOUT s, o remetente tenta de novo (o
  Core reroteia ou guarda; o satélite devolve à fila até o próximo contato).
  Uma falha de 1 s quase não é vista pelo enlace (vizinho só some após
  LINK_TIMEOUT sem beacon), por isso a confirmação. Se o enlace já marcou o
  próximo salto como fora de alcance, o dado é guardado até voltar a ouvi-lo.
- Satélites só trocam mensagens com o hub, enquanto acoplados (regra comum,
  em `RoutingMixin`): por isso a entrega a um satélite é sempre pelo estado
  Direct, no hub.
- O líder de mobilidade (C1) não tem papel especial na transmissão.
"""
from typing import Dict, Optional, Tuple, Union

from src.config import SW_HOP_ACK_TIMEOUT
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import TREE_NEIGHBORS, label

DIRECT = "direct"
Route = Union[str, int, None]


class SwCoreMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self.table: Dict[int, Tuple[Route, int]] = {}  # nó do Core ou satélite → (rota, seq)
        self._held: Dict[str, m.DataMessage] = {}      # id → mensagem guardada
        self._unacked: Dict[str, Tuple[m.DataMessage, int]] = {}  # id → (mensagem, próximo salto)

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

    def _on_contact(self, peer: int) -> None:
        super()._on_contact(peer)
        if self.role == "core" and peer in TREE_NEIGHBORS[self.node_id]:
            entries = [[self.node_id, m.REACH, 0]] + [
                [endpoint, m.UNREACH if route is None else m.REACH, seq]
                for endpoint, (route, seq) in self.table.items() if route != peer]
            self._unicast({"msg_type": m.SYNC, "sender_id": self.node_id, "entries": entries}, peer, control=True)
            self._flush_held()

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

    def _apply(self, kind: str, endpoint: int, seq: int, sender: int) -> None:
        if endpoint == self.node_id:
            return
        route, current = self.table.get(endpoint, (None, -1))
        if kind == m.REACH and seq > current:
            self.table[endpoint] = (sender, seq)
        elif kind == m.UNREACH and (seq > current or (seq == current and route is not None)):
            self.table[endpoint] = (None, seq)
        else:
            return  # anúncio velho ou repetido: não repassa
        self._announce(kind, endpoint, seq, exclude=sender)

    def _on_announce(self, raw: dict) -> None:
        if raw["msg_type"] == m.SYNC:
            for endpoint, kind, seq in raw["entries"]:
                self._apply(kind, endpoint, seq, raw["sender_id"])
        else:
            self._apply(raw["msg_type"], raw["endpoint"], raw["seq"], raw["sender_id"])
        self._flush_held()

    # ── Encaminhamento ────────────────────────────────────────────────────

    def _send(self, message: m.DataMessage, peer: int) -> None:
        """Envia e guarda a mensagem até o HOP_ACK do próximo salto."""
        self._unicast(self._forward_copy(message), peer)
        self._unacked[message["message_id"]] = (message, peer)
        self.provider.schedule_timer(f"hop_ack|{message['message_id']}",
                                     self.provider.current_time() + SW_HOP_ACK_TIMEOUT)

    def _on_hop_timeout(self, msg_id: str) -> None:
        entry = self._unacked.pop(msg_id, None)
        if entry is None:
            return  # confirmada a tempo
        message, peer = entry
        METRICS.hop_retx += 1
        self._log(f"Sem confirmação de {label(peer)} para {message['name']}: tenta de novo")
        if self.role == "core":
            if not self._route(message):
                self._hold(message)
        else:  # satélite: volta à fila; sai de novo pelo hub atual ou no próximo contato
            self._outbox.append(message)
            self._flush_outbox()

    def handle_timer(self, timer: str) -> None:
        super().handle_timer(timer)
        if timer.startswith("hop_ack|"):
            self._on_hop_timeout(timer.split("|", 1)[1])

    def _route(self, message: m.DataMessage) -> bool:
        """Tenta avançar a mensagem; retorna False se ela precisa esperar."""
        destination = message["destination"]
        route, _ = self.table.get(destination, (None, -1))
        if route == DIRECT and destination in self.tethered:
            self._send(message, destination)
            self._note("forwarded", f"Entregou {message['name']} direto a {label(destination)}", "forwarded")
        elif route not in (None, DIRECT) and self._alive(route):
            self._send(message, route)
            self._note("forwarded", f"Repassou {message['name']} a {label(route)}", "forwarded")
        else:
            return False
        return True

    def _hold(self, message: m.DataMessage) -> None:
        self._held[message["message_id"]] = message  # armazenamento ilimitado, sem prazo
        self._note("held", f"Guardou {message['name']} ({label(message['destination'])} inalcançável no momento)")

    def _flush_held(self) -> None:
        for msg_id, msg in list(self._held.items()):
            if self._route(msg):
                del self._held[msg_id]

    def _on_routing(self, raw: dict) -> None:
        kind = raw["msg_type"]
        if kind in (m.REACH, m.UNREACH, m.SYNC):
            self._on_announce(raw)
            return
        if kind == m.HOP_ACK:
            if self._unacked.get(raw["message_id"], (None, None))[1] == raw["sender_id"]:
                del self._unacked[raw["message_id"]]
            return
        if kind != m.DATA:
            return
        self._unicast({"msg_type": m.HOP_ACK, "sender_id": self.node_id, "message_id": raw["message_id"]},
                      raw["sender_id"], control=True)
        if raw["message_id"] in self._seen:  # inclui retransmissão cujo HOP_ACK se perdeu
            self._redundant()
            return
        self._seen.add(raw["message_id"])
        if raw["destination"] == self.node_id:
            self._deliver(raw)
            return
        if self.role == "core" and not self._route(raw):
            self._hold(raw)
