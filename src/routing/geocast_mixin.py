"""
GeoCast: flooding restrito a uma zona de encaminhamento geográfica.

A mensagem carrega a posição da origem (`source_pos`) e a zona de entrega
(círculo de raio `dest_radius` em torno de `dest_pos`, a estação base).
A zona de encaminhamento é o menor retângulo (no plano XY) que contém a
origem e a zona de entrega, ampliado por GEO_ZONE_MARGIN — no estilo do
esquema 1 do LAR (Ko & Vaidya). Um nó só retransmite se a sua posição atual,
obtida da telemetria, estiver dentro dessa zona; caso contrário a mensagem é
podada (`zone_drops`).
"""
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.flooding_mixin import FloodingMixin
from utils.common.config import BASE_STATION_POS, GEO_DEST_RADIUS, GEO_ZONE_MARGIN


class GeocastMixin(FloodingMixin):

    def _originate(self, message: m.DataMessage) -> None:
        message["source_pos"] = self._position or tuple(self._waypoints[0])
        message["dest_pos"] = BASE_STATION_POS
        message["dest_radius"] = GEO_DEST_RADIUS
        super()._originate(message)

    def _should_forward(self, raw: dict) -> bool:
        if self._position is None:
            return True
        if not self._in_forwarding_zone(raw, self._position):
            METRICS.zone_drops += 1
            return False
        return True

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
