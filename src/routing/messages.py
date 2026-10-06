"""
Esquemas das mensagens de roteamento (dicionários serializados em JSON).
"""
from typing import Dict, List, Optional, Tuple, TypedDict

Position = Tuple[float, float, float]

# Valores de `msg_type`
DATA = "routing_data"      # mensagem de dados (Flooding / GeoCast / Árvore)
BUNDLE = "dtn_bundle"      # lote de mensagens em transferência de custódia (DTN)
ACK = "dtn_ack"            # confirmação de custódia (DTN)
BEACON = "beacon"          # anúncio periódico de posição (DTN e Árvore)


class DataMessage(TypedDict, total=False):
    msg_type: str
    message_id: str         # "<origem>:<sequência>", único na simulação
    name: str               # rótulo do fluxo (ex.: CMD_MISSAO, TELEM_S1_3)
    origin_id: int
    destination: int
    dest_pos: Optional[Position]  # posição do destino na criação (serviço de localização)
    sender_id: int          # último nó que transmitiu
    created_at: float
    hops: int               # saltos de rádio percorridos até aqui
    # Flooding / GeoCast
    ttl: int
    # GeoCast
    source_pos: Position
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
