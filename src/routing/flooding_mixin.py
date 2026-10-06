"""
Flooding com supressão de duplicatas e limite por TTL.

Cada nó retransmite uma mensagem no máximo uma vez (tabela `_seen`).
O TTL limita o número de saltos: quem recebe com TTL restante zero descarta.
O destino entrega e não retransmite. Não há armazenamento: se não existir
caminho até o destino no instante da inundação, a mensagem se perde.
"""
from src.config import FLOOD_TTL
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin


class FloodingMixin(RoutingMixin):

    def _originate(self, message: m.DataMessage) -> None:
        message["ttl"] = FLOOD_TTL
        self._seen.add(message["message_id"])
        self._broadcast(message)

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

        ttl = raw["ttl"] - 1
        if ttl <= 0:
            METRICS.ttl_drops += 1
            self._note("ttl_drop", f"Descartou {raw['name']} (TTL esgotado)", "ttl_drops")
            return
        if not self._should_forward(raw):
            return

        self._broadcast({
            **raw,
            "ttl": ttl,
            "hops": raw["hops"] + 1,
            "sender_id": self.provider.get_id(),
        })
        self._note("forwarded", f"Retransmitiu {raw['name']} (TTL={ttl})", "forwarded")

    def _should_forward(self, raw: dict) -> bool:
        """Flooding puro encaminha sempre; o GeoCast restringe por zona."""
        return True
