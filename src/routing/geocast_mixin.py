"""
GeoCast: flooding restrito a uma zona de encaminhamento geográfica.

A mensagem carrega a posição da origem (`source_pos`) e a zona de entrega
(círculo de raio `dest_radius` em torno de `dest_pos`, a posição do destino
no momento da criação). A zona de encaminhamento é o menor retângulo (plano
XY) que contém a origem e a zona de entrega, ampliado por GEO_ZONE_MARGIN —
no estilo do esquema 1 do LAR (Ko & Vaidya). Um nó só retransmite se sua
posição atual estiver dentro da zona; caso contrário poda a mensagem.
"""
from src.config import GEO_DEST_RADIUS, GEO_ZONE_MARGIN
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.flooding_mixin import FloodingMixin


class GeocastMixin(FloodingMixin):

    def _originate(self, message: m.DataMessage) -> None:
        message["source_pos"] = self._position
        message["dest_radius"] = GEO_DEST_RADIUS
        super()._originate(message)

    def _should_forward(self, raw: dict) -> bool:
        if raw.get("dest_pos") is None or self._in_forwarding_zone(raw, self._position):
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
