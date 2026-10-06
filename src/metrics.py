"""
Métricas de roteamento, coletadas durante a simulação (nada é fixado à mão).

Definições
----------
- Mensagem criada: um UAV recebe dados de um sensor e gera uma mensagem
  de roteamento destinada à estação base.
- Entrega: primeira chegada de uma mensagem à estação base.
  Chegadas repetidas contam como `duplicate_deliveries`.
- PDR: entregas / mensagens criadas.
- Latência: instante da entrega − `created_at` (relógio global da simulação;
  num sistema real isso exigiria relógios sincronizados, ex.: GPS).
- Transmissões de dados: todo envio (broadcast ou unicast) que carrega
  mensagens de roteamento, incluindo a primeira transmissão da origem.
- Transmissões de controle: beacons e ACKs de custódia.
- Recepções redundantes: um nó recebe uma mensagem que já tinha visto.
- Heartbeats do template (coleta de sensores) não entram nas contagens:
  são iguais para todos os protocolos.
"""
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Dict, List


@dataclass
class RoutingMetrics:
    created: int = 0
    data_tx: int = 0
    control_tx: int = 0
    redundant_receptions: int = 0
    duplicate_deliveries: int = 0
    ttl_drops: int = 0
    zone_drops: int = 0
    buffer_drops: int = 0
    latencies: Dict[str, float] = field(default_factory=dict)
    hops: Dict[str, int] = field(default_factory=dict)

    def reset(self) -> None:
        self.__init__()

    def record_delivery(self, message: dict, now: float) -> None:
        message_id = message["message_id"]
        if message_id in self.latencies:
            self.duplicate_deliveries += 1
            return
        self.latencies[message_id] = now - message["created_at"]
        self.hops[message_id] = message["hops"]

    def summary(self) -> Dict[str, float]:
        delivered = len(self.latencies)
        lat: List[float] = list(self.latencies.values())
        hops: List[int] = list(self.hops.values())
        return {
            "created": self.created,
            "delivered": delivered,
            "pdr": 100.0 * delivered / self.created if self.created else 0.0,
            "lat_mean": mean(lat) if lat else float("nan"),
            "lat_median": median(lat) if lat else float("nan"),
            "hops_mean": mean(hops) if hops else float("nan"),
            "data_tx": self.data_tx,
            "control_tx": self.control_tx,
            "tx_per_delivery": (self.data_tx + self.control_tx) / delivered if delivered else float("nan"),
            "redundant_receptions": self.redundant_receptions,
            "duplicate_deliveries": self.duplicate_deliveries,
            "ttl_drops": self.ttl_drops,
            "zone_drops": self.zone_drops,
            "buffer_drops": self.buffer_drops,
        }


METRICS = RoutingMetrics()
