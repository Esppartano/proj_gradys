"""
Roteamento por Árvore Geradora sobre a formação em V (protocolo do Swarm Core).

Árvore estática da formação: Torre → C1 → asa esquerda (C2→C3→C4→C5) e
asa direita (C6→C7→C8→C9). Os satélites ficam fora da árvore.

- Detecção de enlace: todos emitem beacons. Se o pai não é ouvido há mais de
  NEIGHBOR_TIMEOUT, o nó se liga ao ancestral vivo mais próximo (ex.: quando C4
  sai para a ronda, C5 passa a usar C3). Nada depende do relógio da simulação.
- Destino vizinho: se o destino é ouvido diretamente, envio direto por unicast.
- Satélite → qualquer destino: injeta no nó do Core mais próximo que ele ouve.
- Destino = torre: sobe pela árvore (pai efetivo a cada salto).
- Destino = satélite: a mensagem se espalha pela árvore por unicast (uma cópia
  por nó, sem broadcast). Cada nó guarda sua cópia por TREE_HOLD_TIME e a
  entrega se ouvir o satélite. Várias cópias podem chegar (entregas duplicadas).
- Sem próximo salto disponível, a mensagem espera e é reavaliada a cada beacon.
"""
from math import dist
from typing import Dict, List, Optional, Tuple

from src.config import TREE_HOLD_TIME
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import CORE, TOWER, label

PARENT = {1: TOWER, 2: 1, 3: 2, 4: 3, 5: 4, 6: 1, 7: 6, 8: 7, 9: 8}
CHILDREN: Dict[int, List[int]] = {n: [] for n in [TOWER] + CORE}
for _child, _parent in PARENT.items():
    CHILDREN[_parent].append(_child)
TREE_NODES = set(CHILDREN)


class TreeMixin(RoutingMixin):

    uses_beacons = True

    def initialize(self) -> None:
        super().initialize()
        self._pending: List[Tuple[m.DataMessage, Optional[int]]] = []  # (msg, veio de)
        self._hold: Dict[str, Tuple[m.DataMessage, float]] = {}       # id → (msg, expira em)

    # ── Estrutura da árvore com detecção de enlace ────────────────────────

    def effective_parent(self) -> Optional[int]:
        parent = PARENT.get(self.provider.get_id())
        while parent is not None:
            if self._alive(parent):
                return parent
            parent = PARENT.get(parent)
        return None

    def effective_children(self) -> List[int]:
        result, stack = [], list(CHILDREN.get(self.provider.get_id(), []))
        while stack:
            child = stack.pop(0)
            if self._alive(child):
                result.append(child)
            else:
                stack.extend(CHILDREN[child])  # filho ausente: adota os netos
        return result

    # ── Roteamento ────────────────────────────────────────────────────────

    def _originate(self, message: m.DataMessage) -> None:
        self._seen.add(message["message_id"])
        message["hops"] = 0
        self._route(message, came_from=None)

    def _send(self, message: m.DataMessage, peer_id: int) -> None:
        self._unicast({**message, "hops": message["hops"] + 1, "sender_id": self.provider.get_id()}, peer_id)

    def _route(self, message: m.DataMessage, came_from: Optional[int]) -> None:
        my_id = self.provider.get_id()
        destination = message["destination"]

        if self._alive(destination):
            self._send(message, destination)
            self._note("forwarded", f"Entregou {message['name']} direto a {label(destination)}", "forwarded")
            return

        if my_id not in TREE_NODES:  # satélite: injeta no Core mais próximo
            core = {p: pos for p, pos in self._fresh_neighbors().items() if p in TREE_NODES}
            if not core:
                self._pending.append((message, came_from))
                return
            entry = min(core, key=lambda p: dist(core[p], self._position))
            self._send(message, entry)
            self._note("forwarded", f"Injetou {message['name']} na árvore via {label(entry)}", "forwarded")
            return

        if destination in TREE_NODES:  # torre: sobe pela árvore
            parent = self.effective_parent()
            if parent is None:
                self._pending.append((message, came_from))
                return
            self._send(message, parent)
            self._note("forwarded", f"Repassou {message['name']} ao pai {label(parent)}", "forwarded")
            return

        # Satélite como destino: espalha pela árvore e guarda uma cópia
        targets = [n for n in [self.effective_parent(), *self.effective_children()]
                   if n is not None and n != came_from]
        for peer_id in targets:
            self._send(message, peer_id)
        self._hold[message["message_id"]] = (message, self.provider.current_time() + TREE_HOLD_TIME)
        if targets:
            names = ", ".join(label(t) for t in targets)
            self._note("forwarded", f"Espalhou {message['name']} na árvore → {names}", "forwarded", len(targets))

    # ── Eventos ───────────────────────────────────────────────────────────

    def _on_routing(self, raw: dict) -> None:
        if raw["msg_type"] != m.DATA:
            return
        if raw["destination"] == self.provider.get_id():
            self._deliver(raw)
            return
        if raw["message_id"] in self._seen:
            METRICS.redundant_receptions += 1
            self.stats["redundant"] += 1
            return
        self._seen.add(raw["message_id"])
        self._route(raw, came_from=raw["sender_id"])

    def _on_beacon(self, sender: int) -> None:
        now = self.provider.current_time()
        for msg_id, (msg, expires) in list(self._hold.items()):
            if now > expires:
                del self._hold[msg_id]
                METRICS.expired += 1
                self.stats["expired"] += 1
            elif msg["destination"] == sender:
                del self._hold[msg_id]
                self._send(msg, sender)
                self._note("forwarded", f"Entregou {msg['name']} a {label(sender)} ao ouvi-lo", "forwarded")

        pending, self._pending = self._pending, []
        for msg, came_from in pending:
            self._route(msg, came_from)
