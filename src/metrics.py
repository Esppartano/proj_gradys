"""
Métricas de roteamento, coletadas durante a simulação (nada é fixado à mão).

Definições
----------
- Mensagem criada: cada acoplamento de um satélite gera uma mensagem para o
  satélite do eixo oposto.
- Entrega: primeira chegada da mensagem ao destino; repetições contam como
  `duplicate_deliveries`.
- PDR: entregas / mensagens criadas.
- Latência: instante da entrega − `created_at` (relógio global da simulação;
  na prática exigiria relógios sincronizados, ex.: GPS).
- Tx de dados: todo envio (broadcast ou unicast) que carrega mensagens de dados.
- Msgs dados tx: mensagens de dados transmitidas, contando cada uma dentro de
  um lote do DTN (compara a carga útil, já que o DTN agrupa mensagens).
- Tx de controle: mensagens de controle do protocolo (anúncios de alcance do
  SwCore, vetores-resumo do DTN, ACKs do receptor no Flooding, buscas e
  respostas de rota do GeoCast). A camada de enlace/formação (beacons e
  handshake) é igual para todos e fica de fora.
- Rx: recepções de pacotes de roteamento (um broadcast conta uma vez por ouvinte).
- Energia: E_TX·(tx dados + tx controle) + E_RX·rx. A energia de movimento é
  igual em todos os protocolos (mesma mobilidade) e não entra na comparação.
"""
import json
from bisect import bisect_left
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Dict, List, Tuple

from src import scenario
from src.config import E_RX, E_TX
from src.scenario import TREE_NEIGHBORS, failure_windows

# ── Energia por nó (extra do T2; não entra nas métricas do enunciado) ──────
# Critério de medição:
# - Comunicação: todo pacote que o nó transmite conta E_TX e todo pacote que ele
#   recebe conta E_RX (um broadcast conta uma recepção por ouvinte). O nó em falha
#   não transmite nem recebe, então não conta. Os pacotes são separados em classes:
#     enlace    = beacons e handshake de acoplamento (msg_type "link*"); no SwCore do
#                 professor, os beacons do Core também levam a RT do Core;
#     coleta    = leituras dos sensores entregues aos satélites ("sensor_data");
#     protocolo = todo o resto (Pub/Sub e SwCore: pedidos, entregas, syncs, RT de
#                 satélites, confirmações de upload).
#   Unidade relativa (a mesma do T1), não joules.
# - Voo: distância percorrida = soma dos deslocamentos entre telemetrias consecutivas
#   (a cada MOBILITY_UPDATE s); tempo em movimento = soma dos intervalos em que o nó
#   se deslocou mais que MOVING_EPS. Dados brutos, sem coeficientes físicos.
PACKET_CLASSES = ("protocolo", "enlace", "coleta")
MOVING_EPS = 1e-3  # m


def packet_class(message: str) -> str:
    try:
        kind = json.loads(message).get("msg_type") or ""
    except (json.JSONDecodeError, AttributeError):
        return "protocolo"
    if kind.startswith("link"):
        return "enlace"
    return "coleta" if kind == "sensor_data" else "protocolo"


@dataclass
class RoutingMetrics:
    created: int = 0
    data_tx: int = 0
    data_msgs_tx: int = 0
    control_tx: int = 0
    rx: int = 0
    redundant_receptions: int = 0
    duplicate_deliveries: int = 0
    ttl_drops: int = 0
    pruned: int = 0            # retransmissões evitadas (self-pruning / fora da zona-alvo)
    no_route: int = 0          # GeoCast: sem vizinho que avance e sem rota pela busca
    bypasses: int = 0          # GeoCast: vazios contornados pela busca de rota
    acks_received: int = 0     # Flooding: ACKs que chegaram de volta à origem
    hop_retx: int = 0          # SwCore: retransmissões por falta de HOP_ACK do próximo salto
    latencies: Dict[str, float] = field(default_factory=dict)
    hops: Dict[str, int] = field(default_factory=dict)
    # SwCore, para o tempo de recuperação após falha: (instante, receptor, remetente)
    syncs: List[Tuple[float, int, int]] = field(default_factory=list)  # SYNC aplicado
    acks: List[Tuple[float, int, int]] = field(default_factory=list)   # HOP_ACK que confirmou um dado
    # SwCore do professor: (nó, instante, relays de que as rotas do nó dependem)
    rt_snapshots: List[Tuple[int, float, frozenset]] = field(default_factory=list)
    # Energia por nó (ver critério no topo): nó → classe → pacotes; voo por nó
    node_tx: Dict[int, Dict[str, int]] = field(default_factory=dict)
    node_rx: Dict[int, Dict[str, int]] = field(default_factory=dict)
    node_dist: Dict[int, float] = field(default_factory=dict)
    node_moving: Dict[int, float] = field(default_factory=dict)

    def count_tx(self, node: int, message: str) -> None:
        per = self.node_tx.setdefault(node, {})
        kind = packet_class(message)
        per[kind] = per.get(kind, 0) + 1

    def count_rx(self, node: int, message: str) -> None:
        per = self.node_rx.setdefault(node, {})
        kind = packet_class(message)
        per[kind] = per.get(kind, 0) + 1

    def record_motion(self, node: int, step: float, interval: float) -> None:
        self.node_dist[node] = self.node_dist.get(node, 0.0) + step
        if step > MOVING_EPS:
            self.node_moving[node] = self.node_moving.get(node, 0.0) + interval

    def register_node(self, node: int) -> None:
        """Garante uma linha para o nó mesmo que ele não transmita, receba nem se mova."""
        self.node_dist.setdefault(node, 0.0)

    def energy_by_node(self) -> List[Dict[str, object]]:
        """Uma linha por nó que apareceu na simulação (ver critério no topo)."""
        nodes = sorted(set(self.node_tx) | set(self.node_rx) | set(self.node_dist))
        rows = []
        for node in nodes:
            tx, rx = self.node_tx.get(node, {}), self.node_rx.get(node, {})
            row = {"node": node, "role": energy_role(node)}
            for kind in PACKET_CLASSES:
                row[f"tx_{kind}"] = tx.get(kind, 0)
                row[f"rx_{kind}"] = rx.get(kind, 0)
                row[f"e_{kind}"] = E_TX * tx.get(kind, 0) + E_RX * rx.get(kind, 0)
            row["e_total"] = sum(row[f"e_{kind}"] for kind in PACKET_CLASSES)
            row["dist"] = self.node_dist.get(node, 0.0)
            row["moving"] = self.node_moving.get(node, 0.0)
            rows.append(row)
        return rows

    def reset(self) -> None:
        self.__init__()

    def recovery(self, duration: float) -> Dict[str, float]:
        """Para cada falha de core (janela [início, fim)), quanto tempo após o fim:
        - roteamento: até o core e cada vizinho da árvore aplicarem o SYNC um do
          outro (tabela ressincronizada nos dois sentidos);
        - dados: até o primeiro dado confirmado (HOP_ACK) enviado pelo core ou a ele.
        Falhas sem o evento até o fim da simulação ficam de fora da média."""
        sync_times = [t for t, _, _ in self.syncs]
        ack_times = [t for t, _, _ in self.acks]
        routing, data = [], []
        windows = failure_windows(duration)
        for _, end, core in windows:  # só eventos após o fim (ignora pacotes em voo no início)
            pending = {(core, p) for p in TREE_NEIGHBORS[core]} | {(p, core) for p in TREE_NEIGHBORS[core]}
            for t, receiver, sender in self.syncs[bisect_left(sync_times, end):]:
                pending.discard((receiver, sender))
                if not pending:
                    routing.append(t - end)
                    break
            for t, receiver, sender in self.acks[bisect_left(ack_times, end):]:
                if core in (receiver, sender):
                    data.append(t - end)
                    break
        nan = float("nan")
        return {
            "failures": len(windows),
            "rec_routing_mean": mean(routing) if routing else nan,
            "rec_routing_max": max(routing) if routing else nan,
            "rec_data_mean": mean(data) if data else nan,
            "rec_data_max": max(data) if data else nan,
        }

    def record_delivery(self, message: dict, now: float) -> bool:
        """Registra a chegada ao destino; retorna True só na primeira vez."""
        message_id = message["message_id"]
        if message_id in self.latencies:
            self.duplicate_deliveries += 1
            return False
        self.latencies[message_id] = now - message["created_at"]
        self.hops[message_id] = message["hops"]
        return True

    def summary(self) -> Dict[str, float]:
        delivered = len(self.latencies)
        lat: List[float] = list(self.latencies.values())
        hops: List[int] = list(self.hops.values())
        tx = self.data_tx + self.control_tx
        return {
            "created": self.created,
            "delivered": delivered,
            "pdr": 100.0 * delivered / self.created if self.created else 0.0,
            "lat_mean": mean(lat) if lat else float("nan"),
            "lat_median": median(lat) if lat else float("nan"),
            "lat_max": max(lat) if lat else float("nan"),
            "hops_mean": mean(hops) if hops else float("nan"),
            "data_tx": self.data_tx,
            "data_msgs_tx": self.data_msgs_tx,
            "control_tx": self.control_tx,
            "rx": self.rx,
            "tx_per_delivery": tx / delivered if delivered else float("nan"),
            "redundant_receptions": self.redundant_receptions,
            "duplicate_deliveries": self.duplicate_deliveries,
            "ttl_drops": self.ttl_drops,
            "pruned": self.pruned,
            "no_route": self.no_route,
            "bypasses": self.bypasses,
            "acks_received": self.acks_received,
            "hop_retx": self.hop_retx,
            "energy": E_TX * tx + E_RX * self.rx,
        }


METRICS = RoutingMetrics()


def record_rt_snapshot(node: int, time: float, uses: frozenset) -> None:
    """Chamado pelo SwCore do professor quando mudam os relays usados pelas rotas de um nó."""
    METRICS.rt_snapshots.append((node, time, uses))


def energy_role(node: int) -> str:
    """Papel para agrupar a energia: PSPeer, demais nós do Core, satélite ou sensor."""
    if node in scenario.PSPEERS:
        return "PSPeer"
    return {"core": "Core (não PSPeer)", "satellite": "Satélite", "sensor": "Sensor"}.get(scenario.role(node), "?")
