"""
Roteamento por Árvore Geradora sobre a formação em V (protocolo do Swarm Core).

Árvore estática da formação: Torre → C1 → asa esquerda (C2→C3→C4→C5) e
asa direita (C6→C7→C8→C9). Os satélites ficam fora da árvore.

- Detecção de enlace: todos emitem beacons. Se o pai não é ouvido há mais de
  NEIGHBOR_TIMEOUT, o nó se liga ao ancestral vivo mais próximo (ex.: se C5
  deixar de ouvir C4, passa a usar C3). A troca não depende do relógio.
- Destino vizinho: se o destino é ouvido diretamente, envio direto por unicast.
- Satélite → qualquer destino: injeta no nó do Core mais próximo que ele ouve.
- Destino = torre: sobe pela árvore (pai efetivo a cada salto).
- Destino = satélite: o nó de entrada escolhe como alvos os TREE_TARGETS nós
  do Core mais próximos da posição do satélite (dest_pos) e a mensagem segue o
  caminho da árvore só até eles, por unicast. Cada alvo guarda uma cópia por
  TREE_HOLD_TIME e a entrega se ouvir o satélite. A posição de cada nó do Core
  vem do slot da formação, conhecido por todos (estrutura virtual).
- Sem próximo salto disponível, a mensagem espera e é reavaliada a cada beacon.
"""
from math import dist
from typing import Dict, List, Optional, Tuple

from src.config import RONDA_END, RONDA_NODE, RONDA_START, TREE_HOLD_TIME, TREE_TARGETS
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import CORE, TOWER, core_slot, label, slot_position

PARENT = {1: TOWER, 2: 1, 3: 2, 4: 3, 5: 4, 6: 1, 7: 6, 8: 7, 9: 8}
CHILDREN: Dict[int, List[int]] = {n: [] for n in [TOWER] + CORE}
for _child, _parent in PARENT.items():
    CHILDREN[_parent].append(_child)
TREE_NODES = set(CHILDREN)


def subtree(node: int) -> set:
    """O nó e todos os seus descendentes na árvore estática."""
    result, stack = set(), [node]
    while stack:
        n = stack.pop()
        result.add(n)
        stack.extend(CHILDREN[n])
    return result


SUBTREE = {n: subtree(n) for n in TREE_NODES}


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

        # Satélite como destino: segue pela árvore até os nós-alvo
        if "targets" not in message:  # nó de entrada na árvore escolhe os alvos
            message = {**message, "targets": self._choose_targets(message)}
        targets = message["targets"]
        if my_id in targets:
            self._hold[message["message_id"]] = (message, self.provider.current_time() + TREE_HOLD_TIME)
        by_hop: Dict[int, List[int]] = {}
        for target in targets:
            if target == my_id:
                continue
            hop = self._next_hop(target)
            if hop is None:  # sem caminho agora: espera o próximo beacon
                self._pending.append(({**message, "targets": [target]}, came_from))
                continue
            by_hop.setdefault(hop, []).append(target)
        for hop, group in by_hop.items():
            self._send({**message, "targets": group}, hop)
            names = ", ".join(label(t) for t in group)
            self._note("forwarded", f"Encaminhou {message['name']} a {label(hop)} (alvo {names})", "forwarded")

    def _choose_targets(self, message: m.DataMessage) -> List[int]:
        """Os TREE_TARGETS nós do Core mais próximos da posição do satélite."""
        t = self.provider.current_time()
        dest_pos = message.get("dest_pos")
        candidates = [n for n in CORE if not (n == RONDA_NODE and RONDA_START <= t < RONDA_END)]
        if dest_pos is None:
            return candidates[:TREE_TARGETS]
        slot = {n: slot_position(core_slot(n, t), t) for n in candidates}
        candidates.sort(key=lambda n: dist(slot[n][:2], dest_pos[:2]))
        return candidates[:TREE_TARGETS]

    def _next_hop(self, target: int) -> Optional[int]:
        """Próximo salto no caminho da árvore até o alvo (desce se o alvo está
        na subárvore deste nó; senão sobe)."""
        if target in SUBTREE[self.provider.get_id()]:
            for child in self.effective_children():
                if target in SUBTREE[child]:
                    return child
            return None
        return self.effective_parent()

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
