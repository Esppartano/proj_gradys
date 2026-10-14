"""
GeoCast: flooding restrito a uma zona de encaminhamento geográfica.

Sem oráculo de posições: a origem usa a posição que o plano compartilhado
atribui ao destino (`planned_position`: a BS no centro; o satélite no ponto do
seu setor). Quando o satélite está em tandem, longe do setor, a previsão erra
— é a fraqueza do GeoCast com mobilidade.

A zona de encaminhamento é o menor retângulo (plano XY) que contém a origem e
a zona de entrega (círculo de raio GEO_DEST_RADIUS em torno de `dest_pos`),
ampliado por GEO_ZONE_MARGIN (esquema 1 do LAR, Ko & Vaidya). Um nó só
retransmite se a sua posição atual estiver na zona; senão poda a mensagem.
"""
from src.config import GEO_DEST_RADIUS, GEO_ZONE_MARGIN
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.flooding_mixin import FloodingMixin
from src.scenario import planned_position


class GeocastMixin(FloodingMixin):

    def _originate(self, message: m.DataMessage) -> None:
        message["source_pos"] = self._position
        message["dest_pos"] = planned_position(message["destination"])
        message["dest_radius"] = GEO_DEST_RADIUS
        super()._originate(message)

    def _should_forward(self, raw: dict) -> bool:
        if self._in_forwarding_zone(raw, self._position):
            return True
        METRICS.zone_drops += 1
        self._note("pruned", f"Podou {raw['name']} (fora da zona de encaminhamento)", "pruned")
        return False

    @staticmethod
    def _in_forwarding_zone(raw: dict, position: m.Position) -> bool:
        sx, sy = raw["source_pos"][:2]
        dx, dy = raw["dest_pos"][:2]
        r = raw["dest_radius"]
        x_min = min(sx, dx - r) - GEO_ZONE_MARGIN
        x_max = max(sx, dx + r) + GEO_ZONE_MARGIN
        y_min = min(sy, dy - r) - GEO_ZONE_MARGIN
        y_max = max(sy, dy + r) + GEO_ZONE_MARGIN
        x, y = position[:2]
        return x_min <= x <= x_max and y_min <= y <= y_max
