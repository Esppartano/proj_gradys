"""
Métricas de roteamento, coletadas durante a simulação (nada é fixado à mão).

Definições
----------
- Mensagem criada: um endpoint gera uma mensagem conforme a agenda de tráfego.
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
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Dict, List, Set

from src.config import E_RX, E_TX


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
    buffer_drops: int = 0
    expired: int = 0
    expired_ids: Set[str] = field(default_factory=set)  # DTN: ids com cópia vencida
    latencies: Dict[str, float] = field(default_factory=dict)
    hops: Dict[str, int] = field(default_factory=dict)

    def reset(self) -> None:
        self.__init__()

    def record_delivery(self, message: dict, now: float) -> bool:
        """Registra a chegada ao destino; retorna True só na primeira vez."""
        message_id = message["message_id"]
        if message_id in self.latencies:
            self.duplicate_deliveries += 1
            return False
        self.latencies[message_id] = now - message["created_at"]
        self.hops[message_id] = message["hops"]
        return True

    def record_expired(self, message_id: str) -> None:
        """DTN: uma cópia venceu. No fim só contam as mensagens nunca entregues
        (várias cópias da mesma mensagem contam uma vez)."""
        self.expired_ids.add(message_id)

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
            "buffer_drops": self.buffer_drops,
            "expired": self.expired + len(self.expired_ids - set(self.latencies)),
            "energy": E_TX * tx + E_RX * self.rx,
        }


METRICS = RoutingMetrics()
