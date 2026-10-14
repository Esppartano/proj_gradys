"""
Flooding com supressão de duplicatas e limite por TTL.

Cada nó retransmite uma mensagem no máximo uma vez (tabela `_seen`).
O TTL (FLOOD_TTL = diâmetro da rede) limita o número de saltos. O destino
entrega e não retransmite.

Armazenamento: só na origem (regra comum a todos os protocolos, em
`RoutingMixin._can_originate`): o satélite acumula o que cria enquanto está
isolado e inunda ao ganhar o primeiro vizinho. Nos intermediários não há
armazenamento: se não existir caminho até o destino no instante da inundação,
a mensagem se perde (não atravessa partições).
"""
from src.config import FLOOD_TTL
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin


class FloodingMixin(RoutingMixin):

    def _originate(self, message: m.DataMessage) -> None:
        self._seen.add(message["message_id"])
        self._broadcast(self._forward_copy(message, ttl=FLOOD_TTL))

    def _on_routing(self, raw: dict) -> None:
        if raw["msg_type"] != m.DATA:
            return
        if raw["destination"] == self.node_id:
            self._deliver(raw)
            return
        if raw["message_id"] in self._seen:
            self._redundant()
            return
        self._seen.add(raw["message_id"])

        ttl = raw["ttl"] - 1
        if ttl <= 0:
            METRICS.ttl_drops += 1
            self._note("ttl_drop", f"Descartou {raw['name']} (TTL esgotado)", "ttl_drops")
            return
        if not self._should_forward(raw):
            return
        self._broadcast(self._forward_copy(raw, ttl=ttl))
        self._note("forwarded", f"Retransmitiu {raw['name']} (TTL={ttl})", "forwarded")

    def _should_forward(self, raw: dict) -> bool:
        """Flooding puro encaminha sempre; o GeoCast restringe por zona."""
        return True
