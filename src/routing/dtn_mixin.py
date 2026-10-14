"""
DTN Store-Carry-Forward com transferência de custódia (cópia única),
guiado por idade do último encontro (estilo FRESH/PRoPHET, só informação local).

- Encontros: cada nó sabe há quanto tempo ouviu cada vizinho (camada de enlace).
  A cada DTN_BEACON s difunde o seu vetor de idades (controle). Quem recebe
  adota idades transitivas: idade do vizinho + DTN_HOP_PENALTY, se for menor
  que a sua. Nenhum nó conhece posições ou o estado global.
- Store: a mensagem fica no buffer do nó (limite DTN_BUFFER_SIZE).
- Carry: o nó segue o seu movimento carregando o buffer.
- Forward: se o destino é vizinho, entrega direto; senão passa a custódia ao
  vizinho que viu o destino há pelo menos DTN_MIN_GAIN s a menos que este nó.
  As mensagens com o mesmo custodiante seguem num único lote (bundle).
- Custódia: o remetente só apaga ao receber o ACK; sem ACK em DTN_ACK_TIMEOUT
  (enlace caiu), as mensagens voltam a ser elegíveis.
"""
from collections import OrderedDict, defaultdict
from math import inf
from typing import Dict, Optional, Tuple

from src.config import DTN_ACK_TIMEOUT, DTN_BEACON, DTN_BUFFER_SIZE, DTN_HOP_PENALTY, DTN_MIN_GAIN
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import label


class DTNMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self._buffer: "OrderedDict[str, m.DataMessage]" = OrderedDict()
        self._in_transfer: Dict[str, float] = {}           # id → instante do envio
        # id → (de quem recebi, quando): reconhece o reenvio por ACK perdido. Não é
        # permanente: a custódia pode voltar legitimamente a um nó por outro caminho.
        self._received: Dict[str, Tuple[int, float]] = {}
        self._met: Dict[int, float] = {}                   # nó → instante do último encontro (transitivo)
        self._peer_ages: Dict[int, Tuple[Dict[int, float], float]] = {}  # vizinho → (idades, recebido em)
        self.provider.schedule_timer("dtn_summary", DTN_BEACON + 0.01 * self.node_id)

    def _can_originate(self) -> bool:
        return True  # a própria mensagem já fica no buffer até haver contato

    # ── Idades de encontro ────────────────────────────────────────────────

    def _age(self, node: int) -> float:
        now = self.provider.current_time()
        if node == self.node_id:
            return 0.0
        last = self._met.get(node, -inf)
        link = self._links.get(node)
        if link is not None:
            last = max(last, link.heard_at)
        return now - last

    def _peer_age(self, peer: int, node: int) -> float:
        if node == peer:
            return 0.0
        entry = self._peer_ages.get(peer)
        if entry is None or node not in entry[0]:
            return inf
        ages, received_at = entry
        return ages[node] + self.provider.current_time() - received_at

    # ── Buffer ────────────────────────────────────────────────────────────

    def _store(self, message: m.DataMessage) -> None:
        if len(self._buffer) >= DTN_BUFFER_SIZE:
            dropped_id, _ = self._buffer.popitem(last=False)
            self._in_transfer.pop(dropped_id, None)
            METRICS.buffer_drops += 1
        self._buffer[message["message_id"]] = message

    def _originate(self, message: m.DataMessage) -> None:
        self._store(message)
        self._try_forward()

    # ── Encaminhamento ────────────────────────────────────────────────────

    def _custodian(self, message: m.DataMessage, neighbors) -> Optional[int]:
        destination = message["destination"]
        if destination in neighbors:
            return destination
        best_id, best_age = None, self._age(destination) - DTN_MIN_GAIN
        for peer in neighbors:
            age = self._peer_age(peer, destination)
            if age < best_age:
                best_id, best_age = peer, age
        return best_id

    def _try_forward(self) -> None:
        if not self._buffer:
            return
        now = self.provider.current_time()
        neighbors = self.neighbors()
        if not neighbors:
            return
        batches = defaultdict(list)
        for msg_id, msg in self._buffer.items():
            if now - self._in_transfer.get(msg_id, -DTN_ACK_TIMEOUT) < DTN_ACK_TIMEOUT:
                continue
            peer = self._custodian(msg, neighbors)
            if peer is not None:
                batches[peer].append(msg)

        for peer, batch in batches.items():
            for msg in batch:
                self._in_transfer[msg["message_id"]] = now
            self._note("handoff", f"Enviou {len(batch)} msg(s) a {label(peer)} (aguardando ACK)",
                       "handed_off", len(batch))
            self._unicast({
                "msg_type": m.BUNDLE,
                "sender_id": self.node_id,
                "messages": [self._forward_copy(msg) for msg in batch],
            }, peer, payload=len(batch))

    def _is_resend(self, msg_id: str, sender: int) -> bool:
        """O mesmo remetente reenviou dentro da janela do ACK (o meu ACK se perdeu)."""
        entry = self._received.get(msg_id)
        return (entry is not None and entry[0] == sender
                and self.provider.current_time() - entry[1] < 2 * DTN_ACK_TIMEOUT)

    # ── Eventos ───────────────────────────────────────────────────────────

    def handle_timer(self, timer: str) -> None:
        if timer == "dtn_summary":
            known = (set(self._met) | set(self._links)) - {self.node_id}  # só nós que este nó já conheceu
            ages = {str(n): self._age(n) for n in known}
            self._broadcast({"msg_type": m.SUMMARY, "sender_id": self.node_id, "ages": ages}, control=True)
            self.provider.schedule_timer("dtn_summary", self.provider.current_time() + DTN_BEACON)
            self._try_forward()
            return
        super().handle_timer(timer)

    def _on_contact(self, peer: int) -> None:
        super()._on_contact(peer)
        self._try_forward()

    def _on_routing(self, raw: dict) -> None:
        kind = raw["msg_type"]
        now = self.provider.current_time()
        if kind == m.SUMMARY:
            peer = raw["sender_id"]
            ages = {int(n): a for n, a in raw["ages"].items()}
            self._peer_ages[peer] = (ages, now)
            for node, age in ages.items():  # idade transitiva
                if node != self.node_id and age + DTN_HOP_PENALTY < self._age(node):
                    self._met[node] = now - age - DTN_HOP_PENALTY
            self._try_forward()
        elif kind == m.BUNDLE:
            received = []
            for msg in raw["messages"]:
                received.append(msg["message_id"])
                if msg["destination"] == self.node_id:
                    self._deliver(msg)
                elif msg["message_id"] in self._buffer or self._is_resend(msg["message_id"], raw["sender_id"]):
                    self._redundant()
                else:
                    self._store(msg)
                    self._received[msg["message_id"]] = (raw["sender_id"], now)
                    self.stats["custody"] += 1
            self._unicast({"msg_type": m.ACK, "sender_id": self.node_id, "ids": received},
                          raw["sender_id"], control=True)
            self._try_forward()
        elif kind == m.ACK:
            for msg_id in raw["ids"]:
                self._buffer.pop(msg_id, None)
                self._in_transfer.pop(msg_id, None)
            self._note("acked", f"{label(raw['sender_id'])} confirmou {len(raw['ids'])} msg(s)")
