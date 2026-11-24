"""
Pub/Sub distribuído sobre o SwCore do professor (T2).

Camadas (enunciado, seção 1): o SwCore do professor (`routing/swcore_professor.py`)
dá as rotas — caminho até o PSPeer mais próximo e até cada nó do Core (path
vector nos beacons) e entrega a satélites com armazenamento até a reconexão. Este
módulo gerencia tópicos, assinaturas e filtros, decide quem deve receber cada
publicação e pede o encaminhamento ao SwCore; o publicador não conhece os
assinantes.

Clientes (os 13 nós)
--------------------
- Região de origem: o eixo do satélite (N/E/S/W) ou C (Core).
- A cada PS_INTERVAL s, cada nó pode assinar um tópico que ainda não assina
  (T1 ou T2), com um filtro sorteado (subconjunto não vazio das regiões). Cada
  nó assina cada tópico no máximo uma vez; o filtro não muda.
- Nós do Core publicam num tópico sorteado (PS_PUBLISH_PROB por sorteio);
  satélites publicam a cada acoplamento.
- Satélites só falam com o Core acoplados: publicam ao acoplar, e uma
  assinatura feita longe do Core vai na próxima solicitação.

PSPeers (PSPEERS, em `scenario.py`)
-----------------------------------
Guardam a fila de cada tópico (todas as publicações, em ordem de criação) e as
assinaturas (assinante, tópico, filtro). Cada publicação tem um dono: o PSPeer
que a recebeu do cliente.

Entrega (regra do enunciado: o assinante recebe toda a fila do tópico desde a
criação, respeitando o filtro; ao retornar e solicitar, só as não lidas)
- Assinante do Core: o dono empurra a publicação aos assinantes que conhece ao
  recebê-la. Ao assinar, o PSPeer que recebe a assinatura manda a fila desde a
  criação (num lote, em ordem); os donos completam com o que ainda não tinha
  chegado a ele. Cada par (assinante, publicação) tem um só remetente.
- Satélite: ao acoplar, solicita as não lidas ao PSPeer mais próximo do hub,
  enviando as suas assinaturas e o que já leu. O PSPeer responde com as
  publicações da fila que passam no filtro e ainda não foram lidas; a resposta
  vai pelo SwCore do professor, que a guarda no Core se o satélite já saiu.

Sincronização (mensagem `pubsub_sync`; enunciado: "multicast de sincronização
contendo as mudanças aos demais nós do core, sem retransmissão; os PSPeers
armazenam, os demais descartam"). Cada mudança que um PSPeer recebe de um cliente
— assinatura nova ou publicação nova (as cópias são completas: tópicos e
assinaturas) — vira um multicast ao Core. Como o rádio do Core só alcança os
vizinhos da árvore, o multicast é uma inundação: cada nó do Core repassa cada
sync uma única vez (TTL SWCORE_MAX_HOPS); PSPeers guardam a mudança, os demais só
repassam e descartam. Sem retransmissão nem ACK: um sync que cruza um nó em falha
se perde para o outro lado. Uma publicação recebida por sync não é empurrada (o
dono já o faz); uma assinatura recebida por sync faz o dono empurrar as suas
publicações que não foram na fila enviada pelo PSPeer do cliente (ver `_ps_on_sub`).

Transporte no Core (mensagem `pubsub`): salto a salto pela RT do SwCore do
professor (`next_hop_core`), sem ACK. Pedido de cliente vai ao PSPeer mais
próximo (`nearest_pspeer`), escolhido pelo 1º nó do Core que o recebe. Sem rota
(ex.: vizinho em falha), a mensagem espera no nó e é tentada de novo a cada
SWCORE_RETRY_INTERVAL s; as seguintes para o mesmo destino esperam atrás dela
(não a ultrapassam). Como no resto do projeto, o nó não sabe que está em falha
(`scenario.failed_core` só simula o canal): o que ele envia nessa janela se perde.

Elegibilidade (gabarito das métricas): o assinante s deve receber a publicação p
se s assina o tópico de p com filtro que contém a região de p e s não é o autor
de p — inclusive publicações anteriores à assinatura.
"""
import json
from bisect import insort
from dataclasses import dataclass, field
from random import Random
from statistics import mean
from typing import Dict, List, Optional, Set, Tuple

from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand

from src import config, scenario
from src.config import (
    PS_INTERVAL, PS_PUBLISH_PROB, PS_REGIONS, PS_SEED, PS_SUBSCRIBE_PROB, PS_TOPICS, SWCORE_MAX_HOPS,
    SWCORE_RETRY_INTERVAL,
)
from src.routing import messages as m
from src.routing.dock_protocol import MSG_DOCK_DELIVER
from src.scenario import PSPEER_ANY, label, region, role

PS_TIMER = "ps_tick"
PS_RETRY_TIMER = "ps_retry"


def eligible(sub: dict, pub: dict) -> bool:
    return sub["subscriber"] != pub["publisher"] and sub["topic"] == pub["topic"] and pub["region"] in sub["filter"]


# ── Métricas de pub/sub (gabarito global, só para medir) ──────────────────

@dataclass
class PubSubMetrics:
    pubs: Dict[str, dict] = field(default_factory=dict)
    subs: Dict[Tuple[int, str], dict] = field(default_factory=dict)   # (assinante, tópico) → assinatura
    sub_known: Dict[str, Dict[int, float]] = field(default_factory=dict)  # assinatura → PSPeer → instante
    # (assinante, pub) → latência, na ordem de chegada (dict preserva a ordem de inserção)
    deliveries: Dict[Tuple[int, str], float] = field(default_factory=dict)
    hops: Dict[Tuple[int, str], int] = field(default_factory=dict)
    duplicates: int = 0

    def reset(self) -> None:
        self.__init__()

    def record_pub(self, pub: dict) -> None:
        self.pubs[pub["id"]] = pub

    def record_sub(self, sub: dict) -> None:
        self.subs[(sub["subscriber"], sub["topic"])] = sub

    def record_known(self, sub_id: str, pspeer: int, now: float) -> None:
        self.sub_known.setdefault(sub_id, {}).setdefault(pspeer, now)

    def record_delivery(self, subscriber: int, pub: dict, now: float, hops: int) -> None:
        """1ª chegada (o cliente descarta e conta as cópias em `duplicates`)."""
        key = (subscriber, pub["id"])
        self.deliveries[key] = now - pub["created_at"]
        self.hops[key] = hops

    def out_of_order(self, hits: Set[Tuple[int, str]]) -> int:
        """Entregas (esperadas) que chegaram depois de uma publicação mais nova do
        mesmo autor no mesmo tópico, para o mesmo assinante (a fila de cada tópico
        é independente: ao assinar T1, a fila antiga de T1 pode chegar depois das
        publicações recentes de T2 do mesmo autor, sem estar fora de ordem)."""
        newest: Dict[Tuple[int, str, int], float] = {}
        late = 0
        for subscriber, pub_id in self.deliveries:  # ordem de chegada
            if (subscriber, pub_id) not in hits:
                continue
            pub = self.pubs[pub_id]
            pair = (subscriber, pub["topic"], pub["publisher"])
            if pub["created_at"] < newest.get(pair, float("-inf")):
                late += 1
            else:
                newest[pair] = pub["created_at"]
        return late

    def expected(self) -> Set[Tuple[int, str]]:
        return {(sub["subscriber"], pub["id"]) for pub in self.pubs.values()
                for sub in self.subs.values() if eligible(sub, pub)}

    def summary(self, duration: float) -> Dict[str, float]:
        expected, delivered = self.expected(), set(self.deliveries)
        hits = delivered & expected  # latência e saltos só das entregas esperadas (sem falsos positivos)
        lat = sorted(self.deliveries[k] for k in hits)
        late = self.out_of_order(hits)
        created = {sub["id"]: sub["created_at"] for sub in self.subs.values()}
        converged = [max(times.values()) - created[sid]
                     for sid, times in self.sub_known.items() if len(times) == len(scenario.PSPEERS)]

        def pct(q: float) -> float:
            return lat[min(len(lat) - 1, int(q * len(lat)))] if lat else float("nan")

        return {
            "ps_pubs": len(self.pubs),
            "ps_subs": len(self.subs),
            "ps_expected": len(expected),
            "ps_delivered": len(hits),
            "ps_mdr": 100.0 * len(hits) / len(expected) if expected else float("nan"),
            "ps_false_pos": len(delivered - expected),
            "ps_false_neg": len(expected - delivered),
            "ps_duplicates": self.duplicates,
            "ps_out_of_order": late,
            "ps_out_of_order_pct": 100.0 * late / len(hits) if hits else float("nan"),
            "ps_throughput": len(hits) / (duration / 60.0),
            "ps_lat_mean": mean(lat) if lat else float("nan"),
            "ps_lat_p95": pct(0.95),
            "ps_lat_p99": pct(0.99),
            "ps_hops_mean": mean(self.hops[k] for k in hits) if hits else float("nan"),
            "ps_sub_conv_mean": mean(converged) if converged else float("nan"),
        }


PS_METRICS = PubSubMetrics()


# ── Estado de um PSPeer ───────────────────────────────────────────────────

class PSPeerState:
    """Cópia de um PSPeer: fila de cada tópico e assinaturas."""

    def __init__(self) -> None:
        self.queue: Dict[str, List[dict]] = {t: [] for t in PS_TOPICS}   # ordem de criação
        self.pub_ids: Set[str] = set()
        self.subs: Dict[Tuple[int, str], dict] = {}                        # (assinante, tópico) → assinatura

    def add_pub(self, pub: dict) -> bool:
        if pub["id"] in self.pub_ids:
            return False
        self.pub_ids.add(pub["id"])
        insort(self.queue[pub["topic"]], pub, key=lambda p: (p["created_at"], p["id"]))
        return True

    def add_sub(self, sub: dict) -> bool:
        key = (sub["subscriber"], sub["topic"])
        if key in self.subs:
            return False
        self.subs[key] = sub
        return True


# ── Cliente (todos os nós) ────────────────────────────────────────────────

class PubSubClient:
    """Assina, publica e recebe. As subclasses dizem como um pedido chega ao PSPeer."""

    def initialize(self) -> None:
        super().initialize()
        self.region = region(self.node_id)
        self._rng = Random(PS_SEED * 1000 + self.node_id)
        self._ps_count = 0
        self.ps_subs: Dict[str, dict] = {}                         # tópico → minha assinatura
        self.ps_read: Dict[str, Set[str]] = {t: set() for t in PS_TOPICS}  # tópico → publicações lidas
        self.provider.schedule_timer(PS_TIMER, self._rng.uniform(0, PS_INTERVAL))

    def _ps_id(self, kind: str) -> str:
        self._ps_count += 1
        return f"{kind}{self.node_id}_{self._ps_count}"

    def _ps_to_pspeer(self, body: dict) -> None:
        raise NotImplementedError

    def _ps_tick(self) -> None:
        if self.provider.current_time() > config.TRAFFIC_END:
            return
        free = [t for t in PS_TOPICS if t not in self.ps_subs]
        if free and self._rng.random() < PS_SUBSCRIBE_PROB:
            self._subscribe(self._rng.choice(free))
        if self.role == "core" and self._rng.random() < PS_PUBLISH_PROB:
            self._publish(self._rng.choice(PS_TOPICS))

    def _subscribe(self, topic: str) -> None:
        regions = sorted(self._rng.sample(PS_REGIONS, self._rng.randint(1, len(PS_REGIONS))))
        sub = {"id": self._ps_id("s"), "subscriber": self.node_id, "topic": topic, "filter": regions,
               "created_at": self.provider.current_time()}
        self.ps_subs[topic] = sub
        PS_METRICS.record_sub(sub)
        self._note("created", f"Assinou {topic} filtro {{{','.join(regions)}}}")
        self._on_subscribed(sub)

    def _on_subscribed(self, sub: dict) -> None:
        raise NotImplementedError

    def _publish(self, topic: str) -> None:
        pub = {"id": self._ps_id("p"), "topic": topic, "region": self.region, "publisher": self.node_id,
               "created_at": self.provider.current_time()}
        PS_METRICS.record_pub(pub)
        self._note("created", f"Publicou {pub['id']} em {topic}", "created")
        self._ps_to_pspeer({"kind": "pub", "pub": pub})

    def _ps_deliver(self, pubs: List[dict], hops: int) -> None:
        """Chegada de publicações (push do dono ou resposta a uma solicitação)."""
        now = self.provider.current_time()
        for pub in pubs:
            read = self.ps_read[pub["topic"]]
            if pub["id"] in read:
                PS_METRICS.duplicates += 1
                continue
            read.add(pub["id"])
            PS_METRICS.record_delivery(self.node_id, pub, now, pub.get("req_hops", 0) + hops)
            self._note("delivered", f"Recebeu {pub['id']} ({pub['topic']}, de {pub['region']})", "received")

    def handle_timer(self, timer: str) -> None:
        if timer == PS_TIMER:
            self._ps_tick()
            self.provider.schedule_timer(PS_TIMER, self.provider.current_time() + PS_INTERVAL)
            return
        super().handle_timer(timer)


# ── Nó do Core (cliente; PSPeer nos de PSPEERS) ───────────────────────────

class PubSubCore(PubSubClient):
    """Vem antes do SwCore do professor na MRO do nó do Core."""

    def initialize(self) -> None:
        super().initialize()
        self.is_pspeer = self.node_id in scenario.PSPEERS
        self.ps_state: Optional[PSPeerState] = PSPeerState() if self.is_pspeer else None
        self._owned: Set[str] = set()          # publicações de que sou dono
        self._ps_pending: List[dict] = []      # mensagens sem rota, em ordem; tentadas de novo
        self._ps_draining = False
        self._ps_deliver_seq = 0
        self._ps_sync_seq = 0
        self._ps_synced: Set[str] = set()      # syncs já repassados (cada um, uma vez)
        self.provider.schedule_timer(PS_RETRY_TIMER, self.provider.current_time() + SWCORE_RETRY_INTERVAL)

    # ── Cliente ───────────────────────────────────────────────────────────

    def _ps_to_pspeer(self, body: dict) -> None:
        self._ps_route({"msg_type": m.PUBSUB, "dest": PSPEER_ANY, "hops": 0, "body": body})

    def _on_subscribed(self, sub: dict) -> None:
        self._ps_to_pspeer({"kind": "sub", "sub": sub})

    # ── Transporte no Core (RT do SwCore do professor) ────────────────────

    def _ps_route(self, msg: dict) -> None:
        """Entra no fim da fila do nó e a fila anda: nada ultrapassa uma mensagem
        mais antiga para o mesmo destino."""
        self._ps_pending.append(msg)
        if not self._ps_draining:  # criada durante uma drenagem (ex.: push ao receber): entra na próxima volta
            self._ps_drain()

    def _ps_drain(self) -> None:
        self._ps_draining = True
        blocked: Set[int] = set()   # destinos sem rota agora: as seguintes esperam atrás
        kept: List[dict] = []
        while self._ps_pending:     # as criadas durante uma volta vêm depois das que já esperavam
            pending, self._ps_pending = self._ps_pending, []
            for msg in pending:
                if msg["dest"] in blocked or not self._ps_try(msg):
                    blocked.add(msg["dest"])
                    kept.append(msg)
        self._ps_pending = kept
        self._ps_draining = False

    def _ps_try(self, msg: dict) -> bool:
        """Entrega aqui ou envia ao próximo salto; False se não há rota agora."""
        if msg["dest"] == PSPEER_ANY:
            peer, _ = self.nearest_pspeer()
            if peer is None:
                return False
            msg["dest"] = peer
        if msg["dest"] == self.node_id:
            self._ps_receive(msg)
            return True
        next_hop = self.next_hop_core(msg["dest"])
        if next_hop is None:
            return False
        if msg["hops"] < SWCORE_MAX_HOPS:  # acima disso, descarta (perda admitida pelo enunciado)
            self.provider.send_communication_command(SendMessageCommand(json.dumps(
                dict(msg, hops=msg["hops"] + 1, sender_id=self.node_id, next_hop=next_hop)), next_hop))
        return True

    def _on_packet(self, raw: dict) -> None:
        if raw.get("msg_type") == m.PUBSUB_SYNC:
            if role(raw.get("sender_id")) == "core":
                self._ps_on_sync(raw)
            return
        if raw.get("msg_type") != m.PUBSUB:
            super()._on_packet(raw)
            return
        sender = raw.get("sender_id")
        if role(sender) == "satellite":
            if sender in self.tethered:  # pedido de um satélite acoplado a mim
                self._ps_route(dict(raw, dest=PSPEER_ANY))
        elif raw.get("next_hop") == self.node_id:
            self._ps_route(raw)

    def _ps_receive(self, msg: dict) -> None:
        body = msg["body"]
        kind = body["kind"]
        if kind == "deliver":
            self._ps_deliver(body["pubs"], msg["hops"])
        elif self.is_pspeer:
            if kind == "pub":
                self._ps_on_pub(dict(body["pub"], req_hops=msg["hops"]))
            elif kind == "sub":
                self._ps_on_sub(body["sub"], from_client=True)
            elif kind == "pull":
                self._ps_on_pull(body)

    # ── PSPeer ────────────────────────────────────────────────────────────

    def _ps_on_pub(self, pub: dict) -> None:
        """Publicação vinda do cliente: entra na fila; sou o dono."""
        if not self.ps_state.add_pub(pub):
            return
        self._owned.add(pub["id"])
        for sub in self.ps_state.subs.values():
            if role(sub["subscriber"]) == "core" and eligible(sub, pub):
                self._ps_push(sub["subscriber"], [pub])
        self._ps_sync({"pub": pub})

    def _ps_on_sub(self, sub: dict, from_client: bool, sent: Optional[List[str]] = None) -> None:
        """Assinatura nova. Um assinante do Core recebe a fila desde a criação, num
        só lote e em ordem de criação, do PSPeer que recebeu a assinatura do cliente;
        o sync leva os ids enviados (`sent`), e cada dono que souber da assinatura
        pelo sync manda só as suas publicações que ficaram de fora (ainda não
        tinham chegado àquele PSPeer). Cada par (assinante, publicação) tem um só
        remetente."""
        if not self.ps_state.add_sub(sub):
            return
        PS_METRICS.record_known(sub["id"], self.node_id, self.provider.current_time())
        backlog: List[dict] = []
        if role(sub["subscriber"]) == "core":
            queue = self.ps_state.queue[sub["topic"]]
            if from_client:
                backlog = [p for p in queue if eligible(sub, p)]
            else:
                skip = set(sent or ())
                backlog = [p for p in queue if p["id"] in self._owned and p["id"] not in skip and eligible(sub, p)]
            if backlog:
                self._ps_push(sub["subscriber"], backlog)
        if from_client:
            self._ps_sync({"sub": sub, "sent": [p["id"] for p in backlog]})

    # ── Sincronização: multicast (inundação) pelo Core, sem retransmissão ─

    def _ps_sync(self, change: dict) -> None:
        self._ps_sync_seq += 1
        sync_id = f"y{self.node_id}_{self._ps_sync_seq}"
        self._ps_synced.add(sync_id)
        self._ps_broadcast_sync({"msg_type": m.PUBSUB_SYNC, "id": sync_id, "hops": 0, "change": change})

    def _ps_broadcast_sync(self, msg: dict) -> None:
        self.provider.send_communication_command(BroadcastMessageCommand(json.dumps(
            dict(msg, hops=msg["hops"] + 1, sender_id=self.node_id))))

    def _ps_on_sync(self, msg: dict) -> None:
        if msg["id"] in self._ps_synced:
            return  # já repassado: cada nó repassa cada sync uma vez
        self._ps_synced.add(msg["id"])
        # Repassa se há outro vizinho do Core além de quem me mandou (a ponta do V não devolve)
        if msg["hops"] < SWCORE_MAX_HOPS and any(n != msg["sender_id"] for n in self.fresh_neighbors()):
            self._ps_broadcast_sync(msg)
        if not self.is_pspeer:
            return  # os demais nós do Core só repassam e descartam
        change = msg["change"]
        if "pub" in change:
            self.ps_state.add_pub(change["pub"])  # entra na fila; quem empurra é o dono
        if "sub" in change:
            self._ps_on_sub(change["sub"], from_client=False, sent=change.get("sent"))

    def _ps_on_pull(self, body: dict) -> None:
        """Satélite acoplado solicitou: responde com as não lidas que passam no filtro."""
        unread = []
        for sub in body["subs"]:
            self._ps_on_sub(sub, from_client=True)
            read = set(body["read"].get(sub["topic"], ()))
            unread += [p for p in self.ps_state.queue[sub["topic"]] if p["id"] not in read and eligible(sub, p)]
        if unread:
            self._ps_to_satellite(body["subscriber"], unread)

    def _ps_push(self, subscriber: int, pubs: List[dict]) -> None:
        body = {"kind": "deliver", "pubs": pubs}
        self._ps_route({"msg_type": m.PUBSUB, "dest": subscriber, "hops": 0, "body": body})

    def _ps_to_satellite(self, sat: int, pubs: List[dict]) -> None:
        """Entrega pelo SwCore do professor: direta se o satélite está acoplado aqui,
        senão pela RT; sem rota, fica no `_core_buffer` até ele reconectar."""
        self._ps_deliver_seq += 1
        entry = {
            "id": f"ps{self.node_id}_{self._ps_deliver_seq}", "origin_face": self.region, "dest_face": region(sat),
            "origin_sat": None, "dest_sat": sat, "created_at": self.provider.current_time(), "hops": 0,
            "payload": {"name": f"{len(pubs)} não lida(s) para {label(sat)}",
                        "ps": {"kind": "deliver", "pubs": pubs}},
        }
        self._core_buffer[entry["id"]] = entry
        self._route(entry)

    def handle_timer(self, timer: str) -> None:
        if timer == PS_RETRY_TIMER:
            self._ps_drain()
            self.provider.schedule_timer(PS_RETRY_TIMER, self.provider.current_time() + SWCORE_RETRY_INTERVAL)
            return
        super().handle_timer(timer)


# ── Satélite (cliente) ────────────────────────────────────────────────────

class PubSubSatellite(PubSubClient):
    """Vem antes do adaptador do satélite na MRO. Só fala com o hub, acoplado."""

    def initialize(self) -> None:
        super().initialize()
        self._ps_outbox: List[dict] = []  # pedidos à espera do acoplamento (ex.: o hub caiu antes do envio)

    def _ps_to_pspeer(self, body: dict) -> None:
        self._ps_outbox.append(body)
        self._ps_flush()

    def _on_subscribed(self, sub: dict) -> None:
        if self._docked():  # acoplado: solicita já; senão, vai ao acoplar
            self._ps_pull()

    def _docked(self) -> bool:
        return self.hub is not None and self.flight == "contato"

    def _ps_flush(self) -> None:
        if not self._docked():
            return
        outbox, self._ps_outbox = self._ps_outbox, []
        for body in outbox:
            self.provider.send_communication_command(SendMessageCommand(json.dumps({
                "msg_type": m.PUBSUB, "dest": PSPEER_ANY, "hops": 1, "body": body, "sender_id": self.node_id,
            }), self.hub))

    def _ps_pull(self) -> None:
        """Solicita as não lidas dos tópicos que assina (com o que já leu)."""
        if not self.ps_subs:
            return
        self._ps_to_pspeer({
            "kind": "pull", "subscriber": self.node_id, "subs": list(self.ps_subs.values()),
            "read": {t: sorted(self.ps_read[t]) for t in self.ps_subs},
        })

    def _on_hub(self, hub) -> None:
        super()._on_hub(hub)
        if self._docked():  # acoplou (um link_ack atrasado, já se afastando, não conta)
            self._ps_flush()
            self._ps_pull()

    def _on_traffic(self, destination: int, name: str) -> None:
        """Acoplamento: publica (no lugar da mensagem ponto a ponto do T1)."""
        self._publish(self._rng.choice(PS_TOPICS))

    def _on_packet(self, raw: dict) -> None:
        ps = (raw.get("payload") or {}).get("ps") if raw.get("msg_type") == MSG_DOCK_DELIVER else None
        if ps is None:
            super()._on_packet(raw)
        elif role(raw.get("sender_id")) == "core":
            self._ps_deliver(ps["pubs"], raw["hops"])
