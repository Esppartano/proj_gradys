"""
DTN Store-Carry-Forward com transferência de custódia (cópia única).

- Store: a mensagem criada fica no buffer do nó (limite DTN_BUFFER_SIZE).
- Carry: o nó segue seu movimento carregando o buffer.
- Forward: a cada beacon recebido, para cada mensagem do buffer:
    * se o destino está entre os vizinhos, envia direto a ele;
    * senão, escolhe o vizinho pelo menos DTN_MIN_PROGRESS metros mais perto
      da posição do destino registrada na mensagem (`dest_pos`).
  As mensagens com o mesmo custodiante seguem num único lote (bundle) por unicast.
- Custódia: o remetente só apaga as mensagens ao receber o ACK; sem ACK em
  DTN_ACK_TIMEOUT (enlace caiu), elas voltam a ser elegíveis.

Limitação: `dest_pos` é a posição do destino na criação; se o destino se
move (satélites), a utilidade geográfica fica desatualizada.
"""
from collections import OrderedDict, defaultdict
from math import dist
from typing import Dict, Optional

from src.config import DTN_ACK_TIMEOUT, DTN_BUFFER_SIZE, DTN_MIN_PROGRESS
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import label


class DTNMixin(RoutingMixin):

    uses_beacons = True

    def initialize(self) -> None:
        super().initialize()
        self._buffer: "OrderedDict[str, m.DataMessage]" = OrderedDict()
        self._in_transfer: Dict[str, float] = {}  # id → instante do envio

    # ── Buffer ────────────────────────────────────────────────────────────

    def _store(self, message: m.DataMessage) -> None:
        if len(self._buffer) >= DTN_BUFFER_SIZE:
            dropped_id, _ = self._buffer.popitem(last=False)
            self._in_transfer.pop(dropped_id, None)
            METRICS.buffer_drops += 1
        self._buffer[message["message_id"]] = message

    def _originate(self, message: m.DataMessage) -> None:
        message["hops"] = 0  # ainda não transmitida; cada transferência soma 1
        self._store(message)
        self._try_forward()

    # ── Encaminhamento ────────────────────────────────────────────────────

    def _custodian(self, message: m.DataMessage, neighbors: Dict[int, m.Position]) -> Optional[int]:
        destination = message["destination"]
        if destination in neighbors:
            return destination
        target = message.get("dest_pos")
        if target is None:
            return None
        best_id, best_distance = None, dist(self._position, target) - DTN_MIN_PROGRESS
        for peer_id, position in neighbors.items():
            distance = dist(position, target)
            if distance < best_distance:
                best_id, best_distance = peer_id, distance
        return best_id

    def _try_forward(self) -> None:
        if not self._buffer:
            return
        now = self.provider.current_time()
        neighbors = self._fresh_neighbors()
        batches = defaultdict(list)
        for msg_id, msg in self._buffer.items():
            if now - self._in_transfer.get(msg_id, -DTN_ACK_TIMEOUT) < DTN_ACK_TIMEOUT:
                continue
            peer_id = self._custodian(msg, neighbors)
            if peer_id is not None:
                batches[peer_id].append(msg)

        for peer_id, batch in batches.items():
            for msg in batch:
                self._in_transfer[msg["message_id"]] = now
            self._note("handoff", f"Enviou {len(batch)} msg(s) a {label(peer_id)} (aguardando ACK)",
                       "handed_off", len(batch))
            self._unicast({
                "msg_type": m.BUNDLE,
                "sender_id": self.provider.get_id(),
                "messages": [
                    {**msg, "hops": msg["hops"] + 1, "sender_id": self.provider.get_id()}
                    for msg in batch
                ],
            }, peer_id)

    # ── Recepção ──────────────────────────────────────────────────────────

    def _on_beacon(self, sender: int) -> None:
        self._try_forward()

    def _on_routing(self, raw: dict) -> None:
        kind = raw["msg_type"]
        if kind == m.BUNDLE:
            received = []
            for msg in raw["messages"]:
                received.append(msg["message_id"])
                if msg["destination"] == self.provider.get_id():
                    self._deliver(msg)
                elif msg["message_id"] in self._buffer:
                    METRICS.redundant_receptions += 1
                    self.stats["redundant"] += 1
                else:
                    self._store(msg)
                    self.stats["custody"] += 1
            self._unicast({
                "msg_type": m.ACK,
                "sender_id": self.provider.get_id(),
                "ids": received,
            }, raw["sender_id"], control=True)
            self._try_forward()
        elif kind == m.ACK:
            for msg_id in raw["ids"]:
                self._buffer.pop(msg_id, None)
                self._in_transfer.pop(msg_id, None)
            self._note("acked", f"{label(raw['sender_id'])} confirmou {len(raw['ids'])} msg(s)")
