"""
DTN Store-Carry-Forward com transferência de custódia (cópia única).

- Store: a mensagem criada fica no buffer do UAV (limite DTN_BUFFER_SIZE).
- Carry: o UAV segue sua patrulha carregando o buffer.
- Forward: a cada beacon recebido, se algum vizinho recente está pelo menos
  DTN_MIN_PROGRESS metros mais perto da base, o UAV envia um lote (bundle)
  por unicast a esse vizinho. A estação base também emite beacons
  (distância zero), então quem passa perto dela entrega tudo.
- Custódia: o remetente só apaga as mensagens ao receber o ACK. Sem ACK em
  DTN_ACK_TIMEOUT (enlace caiu), elas voltam a ser elegíveis para envio.

Encadeando várias transferências, os UAVs formam uma cadeia de mulas até a
base (generalização do cenário multi-mula com rendezvous).
"""
from collections import OrderedDict
from math import dist
from typing import Dict, Tuple

from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from utils.common.config import (
    BASE_STATION_POS,
    BEACON_INTERVAL,
    DTN_ACK_TIMEOUT,
    DTN_BUFFER_SIZE,
    DTN_MIN_PROGRESS,
    NEIGHBOR_TIMEOUT,
)


class DTNMixin(RoutingMixin):

    needs_base_beacon = True

    def initialize(self) -> None:
        super().initialize()
        self._buffer: "OrderedDict[str, m.DataMessage]" = OrderedDict()
        self._in_transfer: Dict[str, float] = {}               # id → instante do envio
        self._neighbors: Dict[int, Tuple[m.Position, float]] = {}  # id → (posição, visto em)
        self._schedule_beacon()

    # ── Beacons ───────────────────────────────────────────────────────────

    def _schedule_beacon(self) -> None:
        self.provider.schedule_timer("beacon", self.provider.current_time() + BEACON_INTERVAL)

    def handle_timer(self, timer: str) -> None:
        if timer == "beacon":
            if self._position is not None:
                self._broadcast({
                    "msg_type": m.BEACON,
                    "sender_id": self.provider.get_id(),
                    "position": self._position,
                }, control=True)
            self._schedule_beacon()
            return
        super().handle_timer(timer)

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

    def _best_custodian(self):
        if self._position is None:
            return None
        now = self.provider.current_time()
        my_distance = dist(self._position, BASE_STATION_POS)
        best_id, best_distance = None, my_distance - DTN_MIN_PROGRESS
        for peer_id, (position, seen_at) in self._neighbors.items():
            if now - seen_at > NEIGHBOR_TIMEOUT:
                continue
            distance = dist(position, BASE_STATION_POS)
            if distance == 0.0:
                return peer_id  # o vizinho é o próprio destino
            if distance < best_distance:
                best_id, best_distance = peer_id, distance
        return best_id

    def _try_forward(self) -> None:
        if not self._buffer:
            return
        peer_id = self._best_custodian()
        if peer_id is None:
            return
        now = self.provider.current_time()
        ready = [
            msg for msg_id, msg in self._buffer.items()
            if now - self._in_transfer.get(msg_id, -DTN_ACK_TIMEOUT) >= DTN_ACK_TIMEOUT
        ]
        if not ready:
            return
        for msg in ready:
            self._in_transfer[msg["message_id"]] = now
        self._unicast({
            "msg_type": m.BUNDLE,
            "sender_id": self.provider.get_id(),
            "messages": [
                {**msg, "hops": msg["hops"] + 1, "sender_id": self.provider.get_id()}
                for msg in ready
            ],
        }, peer_id)

    # ── Recepção ──────────────────────────────────────────────────────────

    def _on_routing(self, raw: dict) -> None:
        kind = raw["msg_type"]
        if kind == m.BEACON:
            self._neighbors[raw["sender_id"]] = (tuple(raw["position"]), self.provider.current_time())
            self._try_forward()
        elif kind == m.BUNDLE:
            received = []
            for msg in raw["messages"]:
                received.append(msg["message_id"])
                if msg["message_id"] in self._buffer:
                    METRICS.redundant_receptions += 1
                    continue
                self._store(msg)
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
