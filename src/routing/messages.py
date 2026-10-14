"""
Esquemas das mensagens de roteamento (dicionários serializados em JSON).
"""
from typing import Dict, List, Optional, Tuple, TypedDict

Position = Tuple[float, float, float]

# Valores de `msg_type`
DATA = "routing_data"      # mensagem de dados (Flooding / GeoCast / SwCore)
BUNDLE = "dtn_bundle"      # lote de mensagens em transferência de custódia (DTN)
ACK = "dtn_ack"            # confirmação de custódia (DTN)
SUMMARY = "dtn_summary"    # vetor de encontros: há quanto tempo vi cada nó (DTN)
REACH = "sw_reach"         # anúncio de alcance de um endpoint (SwCore)
UNREACH = "sw_unreach"     # anúncio de perda de alcance (SwCore)

CONTROL_TYPES = {ACK, SUMMARY, REACH, UNREACH}
ROUTING_TYPES = {DATA, BUNDLE} | CONTROL_TYPES


class DataMessage(TypedDict, total=False):
    msg_type: str
    message_id: str         # "<origem>:<sequência>", único na simulação
    name: str               # rótulo do fluxo (ex.: S1>BS#3)
    origin_id: int
    destination: int
    sender_id: int          # último nó que transmitiu
    created_at: float
    hops: int               # saltos de rádio percorridos até aqui
    # Flooding / GeoCast
    ttl: int
    # GeoCast
    source_pos: Position
    dest_pos: Optional[Position]  # posição prevista do destino pelo plano compartilhado
    dest_radius: float


class BundleMessage(TypedDict):
    msg_type: str
    sender_id: int
    messages: List[DataMessage]


class AckMessage(TypedDict):
    msg_type: str
    sender_id: int
    ids: List[str]


class SummaryMessage(TypedDict):
    msg_type: str
    sender_id: int
    ages: Dict[str, float]  # nó → segundos desde o último encontro


class ReachMessage(TypedDict):
    msg_type: str
    sender_id: int
    endpoint: int
    seq: int                # nº do handshake do endpoint (descarta anúncios velhos)
