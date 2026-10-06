"""
Esquemas das mensagens de roteamento.

Todas as mensagens são dicionários serializados em JSON, como no template.
Mensagens de roteamento usam o campo `msg_type` (o template usa `sender_type`
para heartbeats de UAV e respostas de sensores), então os dois tráfegos não
se confundem.
"""
from typing import Dict, List, Tuple, TypedDict

Position = Tuple[float, float, float]

# Valores de `msg_type`
DATA = "routing_data"      # mensagem de dados (Flooding / GeoCast)
BUNDLE = "dtn_bundle"      # lote de mensagens em transferência de custódia (DTN)
ACK = "dtn_ack"            # confirmação de custódia (DTN)
BEACON = "beacon"          # anúncio de posição (DTN e estação base)


class DataMessage(TypedDict, total=False):
    msg_type: str
    message_id: str         # "<origem>:<sequência>", único na simulação
    origin_id: int
    sender_id: int          # último nó que transmitiu
    created_at: float       # instante de criação (relógio da simulação)
    hops: int               # saltos de rádio percorridos até aqui
    payload: Dict[str, int] # sensor → contagem de pacotes coletados
    # Flooding / GeoCast
    ttl: int
    # GeoCast
    source_pos: Position
    dest_pos: Position
    dest_radius: float


class BundleMessage(TypedDict):
    msg_type: str
    sender_id: int
    messages: List[DataMessage]


class AckMessage(TypedDict):
    msg_type: str
    sender_id: int
    ids: List[str]


class BeaconMessage(TypedDict):
    msg_type: str
    sender_id: int
    position: Position
