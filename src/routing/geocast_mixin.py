"""
GeoCast: encaminhamento guloso até a zona-alvo, contorno de vazios por busca de
rota e inundação local dentro da zona-alvo.

Segue o slide e Choi et al. (2018): usa a geolocalização do destino e a dos
vizinhos para repassar "na direção" do destino, contornando áreas sem
cobertura quando possível; ao chegar à zona-alvo, inunda localmente.

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
    4. nenhum vizinho avança (mínimo local, ex.: ponta do V) → busca de rota
       (Choi et al., seção II.B): difundo uma BUSCA (controle) que se propaga
       salto a salto só por nós da região na direção do destino (a até a minha
       distância + GEO_SEARCH_MARGIN dele), com limite de saltos. O primeiro nó
       mais perto do destino do que eu responde (RESPOSTA, controle), pelo
       caminho inverso. Envio os dados por esse caminho e, a partir de quem
       respondeu, o guloso recomeça;
    5. sem resposta em GEO_SEARCH_TIMEOUT s → descarta ("sem rota"). O GeoCast
       não armazena nos intermediários.
"""
from math import dist
from typing import Dict

from src.config import FLOOD_TTL, GEO_DEST_RADIUS, GEO_SEARCH_MARGIN, GEO_SEARCH_TIMEOUT
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import label, planned_position

GREEDY, ZONE = "greedy", "zone"


class GeocastMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self._searching: Dict[str, dict] = {}  # busca → mensagem à espera de rota
        self._seen_searches: set = set()
        self._search_count = 0                 # cada tentativa tem id próprio (timer não confunde)

    def _originate(self, message: m.DataMessage) -> None:
        message["dest_pos"] = planned_position(message["destination"])
        message["mode"] = GREEDY
        self._seen.add(message["message_id"])
        self._forward(message)

    def _in_zone(self, raw: dict) -> bool:
        return dist(self._position, raw["dest_pos"]) <= GEO_DEST_RADIUS

    # ── Fases 1 a 4 ───────────────────────────────────────────────────────

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
        self._start_search(raw)

    # ── Contorno de vazios: busca de rota (Choi et al., II.B) ─────────────

    def _start_search(self, raw: dict) -> None:
        if not self.neighbors():  # isolado: não há por onde buscar
            self._drop_no_route(raw)
            return
        self._search_count += 1
        search_id = f"{self.node_id}:{self._search_count}"
        self._searching[search_id] = raw
        self._seen_searches.add(search_id)
        self._broadcast({
            "msg_type": m.GEO_SEARCH, "sender_id": self.node_id, "search_id": search_id,
            "target": raw["dest_pos"], "stuck_dist": dist(self._position, raw["dest_pos"]),
            "destination": raw["destination"], "message_id": raw["message_id"],
            "path": [self.node_id], "ttl": FLOOD_TTL,
        }, control=True)
        self.provider.schedule_timer(f"geo_search:{search_id}",
                                     self.provider.current_time() + GEO_SEARCH_TIMEOUT)
        self._note("search", f"Mínimo local: buscou rota para {raw['name']}")

    def _on_search(self, raw: dict) -> None:
        if raw["search_id"] in self._seen_searches:
            return
        self._seen_searches.add(raw["search_id"])
        path = raw["path"] + [self.node_id]
        my_dist = dist(self._position, raw["target"])
        # Quem já viu a mensagem não responde (evita devolvê-la ao caminho de onde veio)
        fresh = raw["message_id"] not in self._seen
        if self.node_id == raw["destination"] or (fresh and my_dist < raw["stuck_dist"]):
            self._send_reply(raw["search_id"], path)  # achei quem avança: respondo
        elif my_dist <= raw["stuck_dist"] + GEO_SEARCH_MARGIN and raw["ttl"] > 1:
            self._broadcast({**raw, "sender_id": self.node_id, "path": path, "ttl": raw["ttl"] - 1},
                            control=True)

    def _send_reply(self, search_id: str, path: list) -> None:
        """A resposta volta pelo caminho inverso da busca."""
        previous = path[path.index(self.node_id) - 1]
        self._unicast({"msg_type": m.GEO_REPLY, "sender_id": self.node_id,
                       "search_id": search_id, "path": path}, previous, control=True)

    def _on_reply(self, raw: dict) -> None:
        path = raw["path"]
        if path[0] != self.node_id:  # intermediário: repassa para trás
            self._send_reply(raw["search_id"], path)
            return
        message = self._searching.pop(raw["search_id"], None)
        if message is None:  # outra resposta já foi usada (ou a busca expirou)
            return
        METRICS.bypasses += 1
        self._unicast(self._forward_copy(message, route=path), path[1])
        self._note("forwarded", f"Contornou o vazio: {message['name']} via {label(path[1])}", "forwarded")

    def _on_routed(self, raw: dict) -> None:
        """Dados seguindo o caminho achado pela busca."""
        self._seen.add(raw["message_id"])
        path = raw["route"]
        i = path.index(self.node_id)
        if i < len(path) - 1:
            self._unicast(self._forward_copy(raw), path[i + 1])
            self._note("forwarded", f"Repassou {raw['name']} a {label(path[i + 1])} (contorno)", "forwarded")
            return
        message = {k: v for k, v in raw.items() if k != "route"}  # sou quem respondeu: volta o guloso
        self._forward(message)

    def _drop_no_route(self, raw: dict) -> None:
        METRICS.no_route += 1
        self._note("ttl_drop", f"Descartou {raw['name']} (nenhum vizinho mais perto do destino)")

    # ── Eventos ───────────────────────────────────────────────────────────

    def handle_timer(self, timer: str) -> None:
        if timer.startswith("geo_search:"):
            message = self._searching.pop(timer.split(":", 1)[1], None)
            if message is not None:  # ninguém respondeu a tempo
                self._drop_no_route(message)
            return
        super().handle_timer(timer)

    def _on_routing(self, raw: dict) -> None:
        kind = raw["msg_type"]
        if kind == m.GEO_SEARCH:
            self._on_search(raw)
            return
        if kind == m.GEO_REPLY:
            self._on_reply(raw)
            return
        if kind != m.DATA:
            return
        if raw["destination"] == self.node_id:
            self._deliver(raw)
            return
        if "route" in raw:  # caminho do contorno: passa mesmo por quem já viu a mensagem
            self._on_routed(raw)
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
