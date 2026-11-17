"""
Pub/Sub distribuído sobre o SwCore (T2).

Papéis
------
- Clientes: os 13 nós. Cada um tem uma região de origem: o eixo do satélite
  (S1 E, S2 N, S3 W, S4 S) ou C para os nós do Core. A cada PS_INTERVAL s, cada
  nó sorteia uma assinatura nova (tópico + filtro de regiões não vazio; uma
  assinatura nova de um tópico substitui o filtro anterior desse tópico) e, no
  Core, uma publicação num tópico sorteado. Satélites publicam a cada
  acoplamento (no lugar da mensagem ponto a ponto do T1).
- PSPeers (PSPEERS, em `scenario.py`): alguns nós do Core, não todos — o líder
  C1 e outros a ≤ 2 saltos, de modo que todo nó do Core está a ≤ 2 saltos de um
  PSPeer. Cada PSPeer guarda uma réplica do estado: publicações por tópico e
  histórico de assinaturas de cada nó.

Transporte: tudo é mensagem de dados do SwCore (hop a hop, com HOP_ACK), sem
rádio de longo alcance. O conteúdo de pub/sub vai no campo `ps`:
- `request` (cliente → PSPeer mais próximo): uma assinatura ou uma publicação.
  O satélite não sabe em que nó do Core vai acoplar: endereça PSPEER_ANY, e o
  primeiro nó do Core que a recebe escolhe o PSPeer mais próximo dele.
- `sync` (PSPeer → outros PSPeers): replica a mudança.
- `notify` (PSPeer → assinante): uma publicação. Para um satélite, o SwCore a
  guarda no Core até ele acoplar.

Casamento sem duplicata: cada publicação tem um dono, o PSPeer que a recebeu
do cliente; só o dono a notifica, e ele lembra a quem já mandou. O dono
notifica (a) ao receber a publicação, todos os assinantes que já conhece; (b) ao
saber de uma assinatura (do cliente ou por sync), as suas publicações que ela
deveria ter recebido. Assim, uma assinatura e uma publicação que chegam ao
mesmo tempo a PSPeers diferentes não se perdem: o sync da assinatura chega ao
dono da publicação.

Regra de entrega (também usada como gabarito nas métricas): o assinante s
recebe a publicação p se s ≠ autor de p e o filtro de s para o tópico de p,
vigente no instante em que p foi criada, contém a região de p. Não há entrega
do histórico anterior à assinatura.
"""
from bisect import bisect_right
from dataclasses import dataclass, field
from random import Random
from statistics import mean
from typing import Dict, List, Optional, Set, Tuple

from src import config
from src.config import PS_INTERVAL, PS_PUBLISH_PROB, PS_REGIONS, PS_SEED, PS_SUBSCRIBE_PROB, PS_TOPICS
from src.routing import messages as m
from src.routing.swcore_mixin import SwCoreMixin
from src.scenario import PSPEERS, PSPEER_ANY, label, nearest_pspeer, region

PS_TIMER = "ps_tick"


# ── Estado de um PSPeer ───────────────────────────────────────────────────

class PubSubState:
    """Réplica de um PSPeer: publicações e histórico de filtros por assinante."""

    def __init__(self) -> None:
        self.pubs: Dict[str, dict] = {}                              # id → publicação
        self.by_topic: Dict[str, List[dict]] = {t: [] for t in PS_TOPICS}
        # (assinante, tópico) → [(instante, id da assinatura, filtro)] ordenado
        self.subs: Dict[Tuple[int, str], List[Tuple[float, str, List[str]]]] = {}
        self._sub_ids: Set[str] = set()

    def add_pub(self, pub: dict) -> bool:
        if pub["id"] in self.pubs:
            return False
        self.pubs[pub["id"]] = pub
        self.by_topic[pub["topic"]].append(pub)
        return True

    def add_sub(self, sub: dict) -> bool:
        if sub["id"] in self._sub_ids:
            return False
        self._sub_ids.add(sub["id"])
        history = self.subs.setdefault((sub["subscriber"], sub["topic"]), [])
        history.append((sub["created_at"], sub["id"], sub["filter"]))
        history.sort()
        return True

    def subscribers(self, topic: str) -> List[int]:
        return [s for (s, t) in self.subs if t == topic]

    def matches(self, subscriber: int, pub: dict) -> bool:
        return matches(self.subs.get((subscriber, pub["topic"]), []), subscriber, pub)


def matches(history: List[Tuple[float, str, List[str]]], subscriber: int, pub: dict) -> bool:
    """Regra de entrega: filtro vigente quando a publicação foi criada."""
    if subscriber == pub["publisher"]:
        return False
    i = bisect_right(history, pub["created_at"], key=lambda entry: entry[0])
    return i > 0 and pub["region"] in history[i - 1][2]


# ── Métricas de pub/sub (gabarito global, só para medir) ──────────────────

@dataclass
class PubSubMetrics:
    pubs: Dict[str, dict] = field(default_factory=dict)
    subs: Dict[Tuple[int, str], List[Tuple[float, str, List[str]]]] = field(default_factory=dict)
    sub_created: Dict[str, float] = field(default_factory=dict)
    sub_known: Dict[str, List[float]] = field(default_factory=dict)  # instantes em que cada PSPeer soube
    deliveries: Dict[Tuple[int, str], float] = field(default_factory=dict)  # (assinante, pub) → latência
    hops: Dict[Tuple[int, str], int] = field(default_factory=dict)
    duplicates: int = 0

    def reset(self) -> None:
        self.__init__()

    def record_pub(self, pub: dict) -> None:
        self.pubs[pub["id"]] = pub

    def record_sub(self, sub: dict) -> None:
        self.sub_created[sub["id"]] = sub["created_at"]
        history = self.subs.setdefault((sub["subscriber"], sub["topic"]), [])
        history.append((sub["created_at"], sub["id"], sub["filter"]))
        history.sort()

    def record_known(self, sub_id: str, now: float) -> None:
        self.sub_known.setdefault(sub_id, []).append(now)

    def record_delivery(self, subscriber: int, pub: dict, now: float, hops: int) -> bool:
        key = (subscriber, pub["id"])
        if key in self.deliveries:
            self.duplicates += 1
            return False
        self.deliveries[key] = now - pub["created_at"]
        self.hops[key] = hops
        return True

    def expected(self) -> Set[Tuple[int, str]]:
        return {(s, pub["id"]) for pub in self.pubs.values()
                for (s, t), history in self.subs.items()
                if t == pub["topic"] and matches(history, s, pub)}

    def summary(self) -> Dict[str, float]:
        expected, delivered = self.expected(), set(self.deliveries)
        hits = delivered & expected  # latência e saltos só das entregas esperadas (sem falsos positivos)
        lat = sorted(self.deliveries[k] for k in hits)
        converged = [max(times) - self.sub_created[sid]
                     for sid, times in self.sub_known.items() if len(times) == len(PSPEERS)]

        def pct(q: float) -> float:
            return lat[min(len(lat) - 1, int(q * len(lat)))] if lat else float("nan")

        return {
            "ps_pubs": len(self.pubs),
            "ps_subs": len(self.sub_created),
            "ps_expected": len(expected),
            "ps_delivered": len(hits),
            "ps_mdr": 100.0 * len(hits) / len(expected) if expected else float("nan"),
            "ps_false_pos": len(delivered - expected),
            "ps_false_neg": len(expected - delivered),
            "ps_duplicates": self.duplicates,
            "ps_lat_mean": mean(lat) if lat else float("nan"),
            "ps_lat_p95": pct(0.95),
            "ps_lat_p99": pct(0.99),
            "ps_hops_mean": mean(self.hops[k] for k in hits) if hits else float("nan"),
            "ps_sub_conv_mean": mean(converged) if converged else float("nan"),
        }


PS_METRICS = PubSubMetrics()


# ── Nó com pub/sub (cliente em todos; PSPeer em alguns do Core) ───────────

class PubSubMixin(SwCoreMixin):

    def initialize(self) -> None:
        super().initialize()
        self.region = region(self.node_id)
        self.is_pspeer = self.node_id in PSPEERS
        self.ps_state: Optional[PubSubState] = PubSubState() if self.is_pspeer else None
        self._owned: Dict[str, Set[int]] = {}   # publicações de que sou dono → assinantes já notificados
        self._rng = Random(PS_SEED * 1000 + self.node_id)
        self._ps_count = 0
        self.provider.schedule_timer(PS_TIMER, self._rng.uniform(0, PS_INTERVAL))

    # ── Cliente ───────────────────────────────────────────────────────────

    def _ps_id(self, kind: str) -> str:
        self._ps_count += 1
        return f"{kind}{self.node_id}_{self._ps_count}"

    def _ps_tick(self) -> None:
        now = self.provider.current_time()
        if now > config.TRAFFIC_END:
            return
        if self._rng.random() < PS_SUBSCRIBE_PROB:
            regions = sorted(self._rng.sample(PS_REGIONS, self._rng.randint(1, len(PS_REGIONS))))
            sub = {"id": self._ps_id("s"), "subscriber": self.node_id, "topic": self._rng.choice(PS_TOPICS),
                   "filter": regions, "created_at": now}
            PS_METRICS.record_sub(sub)
            self._note("created", f"Assinou {sub['topic']} filtro {{{','.join(regions)}}}")
            self._ps_request({"kind": "request", "sub": sub})
        if self.role == "core" and self._rng.random() < PS_PUBLISH_PROB:
            self._publish(now)

    def _on_traffic(self, destination: int, name: str) -> None:
        """Acoplamento do satélite: publica (no lugar da mensagem do T1)."""
        self._publish(self.provider.current_time())

    def _publish(self, now: float) -> None:
        pub = {"id": self._ps_id("p"), "topic": self._rng.choice(PS_TOPICS), "region": self.region,
               "publisher": self.node_id, "created_at": now}
        PS_METRICS.record_pub(pub)
        self._note("created", f"Publicou {pub['id']} em {pub['topic']}", "created")
        self._ps_request({"kind": "request", "pub": pub})

    def _ps_request(self, ps: dict) -> None:
        if self.is_pspeer:
            self._ps_handle(ps, hops=0)
        else:
            target = nearest_pspeer(self.node_id) if self.role == "core" else PSPEER_ANY
            self._ps_send(target, ps, "req")

    def _ps_send(self, destination: int, ps: dict, tag: str) -> None:
        """Cria uma mensagem de dados do SwCore com conteúdo de pub/sub."""
        message = self._new_message(destination, f"{tag}:{ps.get('pub', ps.get('sub', {})).get('id', '?')}")
        message["ps"] = ps
        self._outbox.append(message)
        self._flush_outbox()

    def _on_notify(self, pub: dict, hops: int) -> None:
        if PS_METRICS.record_delivery(self.node_id, pub, self.provider.current_time(), hops):
            self._note("delivered", f"Recebeu {pub['id']} ({pub['topic']}, de {pub['region']})", "received")

    # ── PSPeer ────────────────────────────────────────────────────────────

    def _ps_handle(self, ps: dict, hops: int) -> None:
        """Pedido de um cliente ou sync de outro PSPeer."""
        state, now = self.ps_state, self.provider.current_time()
        pub, sub = ps.get("pub"), ps.get("sub")
        if pub is not None:
            if ps["kind"] == "request":
                pub = dict(pub, owner=self.node_id, req_hops=hops)
            if not state.add_pub(pub):
                return
            if pub["owner"] == self.node_id:
                self._owned[pub["id"]] = set()
                for subscriber in state.subscribers(pub["topic"]):
                    self._notify_if_match(subscriber, pub)
        if sub is not None:
            if not state.add_sub(sub):
                return
            PS_METRICS.record_known(sub["id"], now)
            for pub_id in self._owned:
                candidate = state.pubs[pub_id]
                if candidate["topic"] == sub["topic"] and candidate["created_at"] >= sub["created_at"]:
                    self._notify_if_match(sub["subscriber"], candidate)
        if ps["kind"] == "request":  # replica a mudança nos outros PSPeers
            change = {"kind": "sync", "pub": pub} if pub is not None else {"kind": "sync", "sub": sub}
            for peer in PSPEERS:
                if peer != self.node_id:
                    self._ps_send(peer, change, "sync")

    def _notify_if_match(self, subscriber: int, pub: dict) -> None:
        sent = self._owned[pub["id"]]
        if subscriber in sent or not self.ps_state.matches(subscriber, pub):
            return
        sent.add(subscriber)
        if subscriber == self.node_id:
            self._on_notify(pub, pub["req_hops"])
        else:
            self._ps_send(subscriber, {"kind": "notify", "pub": pub}, f"ntf>{label(subscriber)}")

    # ── Integração com o SwCore ───────────────────────────────────────────

    def _route(self, message: m.DataMessage) -> bool:
        if message["destination"] == PSPEER_ANY:  # pedido de satélite: o 1º nó do Core escolhe o PSPeer
            message["destination"] = nearest_pspeer(self.node_id)
            if message["destination"] == self.node_id:
                self._deliver(message)
                return True
        return super()._route(message)

    def _deliver(self, message: m.DataMessage) -> None:
        ps = message.get("ps")
        if ps is None:
            return super()._deliver(message)
        if ps["kind"] == "notify":
            self._on_notify(ps["pub"], ps["pub"]["req_hops"] + message["hops"])
        elif self.is_pspeer:
            self._ps_handle(ps, message["hops"])

    def handle_timer(self, timer: str) -> None:
        super().handle_timer(timer)
        if timer == PS_TIMER:
            self._ps_tick()
            self.provider.schedule_timer(PS_TIMER, self.provider.current_time() + PS_INTERVAL)
