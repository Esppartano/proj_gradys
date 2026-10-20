"""
GeoCast: encaminhamento guloso até a zona-alvo e inundação local dentro dela.

Segue o slide e Choi et al. (2018): usa a geolocalização do destino e a dos
vizinhos para repassar "na direção" do destino; ao chegar à zona-alvo, inunda
localmente para achar o destino.

- Posição do destino: a prevista pelo plano compartilhado (`planned_position`:
  o ponto do setor do satélite ou o centro, para a BS). Durante o tandem o
  satélite está longe do setor e a previsão erra: é a fraqueza do GeoCast
  com mobilidade ("precisa de posição precisa").
- Posição dos vizinhos: a anunciada nos beacons de enlace (informação local).
  Distâncias em 3D ("esfera no céu").
- Fases, em cada nó:
    1. ouço o destino → entrego direto (unicast);
    2. estou dentro da zona-alvo (esfera de raio GEO_DEST_RADIUS em torno da
       posição prevista) → inundo localmente (broadcast com TTL); só nós
       dentro da zona retransmitem, os de fora descartam (poda);
    3. senão → unicast ao vizinho mais perto do destino, se ele estiver mais
       perto que eu (guloso);
    4. nenhum vizinho avança (vazio de cobertura, ex.: ponta do V) → descarta
       ("sem rota"). O GeoCast não armazena nos intermediários.
"""
from math import dist

from src.config import FLOOD_TTL, GEO_DEST_RADIUS
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import label, planned_position

GREEDY, ZONE = "greedy", "zone"


class GeocastMixin(RoutingMixin):

    def _originate(self, message: m.DataMessage) -> None:
        message["dest_pos"] = planned_position(message["destination"])
        message["mode"] = GREEDY
        self._seen.add(message["message_id"])
        self._forward(message)

    def _in_zone(self, raw: dict) -> bool:
        return dist(self._position, raw["dest_pos"]) <= GEO_DEST_RADIUS

    def _forward(self, raw: dict) -> None:
        destination, target = raw["destination"], raw["dest_pos"]
        neighbors = self.neighbors()
        if destination in neighbors:
            self._unicast(self._forward_copy(raw), destination)
            self._note("forwarded", f"Entregou {raw['name']} direto a {label(destination)}", "forwarded")
            return
        if self._in_zone(raw):
            self._broadcast(self._forward_copy(raw, mode=ZONE, ttl=FLOOD_TTL))
            self._note("forwarded", f"Chegou à zona-alvo: inundou {raw['name']} localmente", "forwarded")
            return
        best = min(neighbors, key=lambda p: dist(neighbors[p].position, target), default=None)
        if best is not None and dist(neighbors[best].position, target) < dist(self._position, target):
            self._unicast(self._forward_copy(raw), best)
            self._note("forwarded", f"Repassou {raw['name']} a {label(best)} (guloso)", "forwarded")
            return
        METRICS.no_route += 1
        self._note("ttl_drop", f"Descartou {raw['name']} (nenhum vizinho mais perto do destino)")

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
        if raw["mode"] == GREEDY or raw["destination"] in self.neighbors():
            self._forward(raw)  # a fase 1 (ouço o destino → entrego direto) vale nos dois modos
            return
        # Inundação local: só quem está dentro da zona retransmite
        ttl = raw["ttl"] - 1
        if not self._in_zone(raw):
            METRICS.pruned += 1
            self._note("pruned", f"Podou {raw['name']} (fora da zona-alvo)", "pruned")
        elif ttl <= 0:
            METRICS.ttl_drops += 1
            self._note("ttl_drop", f"Descartou {raw['name']} (TTL esgotado)", "ttl_drops")
        else:
            self._broadcast(self._forward_copy(raw, ttl=ttl))
            self._note("forwarded", f"Retransmitiu {raw['name']} na zona-alvo (TTL={ttl})", "forwarded")
