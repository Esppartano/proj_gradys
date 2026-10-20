"""
Esquemas das mensagens de roteamento (dicionários serializados em JSON).
"""
from typing import List, Tuple, TypedDict

Position = Tuple[float, float, float]

# Valores de `msg_type`
DATA = "routing_data"      # mensagem de dados (Flooding / GeoCast / SwCore)
BUNDLE = "dtn_bundle"      # lote de mensagens em transferência de custódia (DTN)
SUMMARY = "dtn_summary"    # vetor-resumo: ids que tenho + ids já entregues (DTN)
FLOOD_ACK = "flood_ack"    # confirmação do receptor, inundada de volta à origem (Flooding)
REACH = "sw_reach"         # anúncio de alcance de um endpoint (SwCore)
UNREACH = "sw_unreach"     # anúncio de perda de alcance (SwCore)

CONTROL_TYPES = {SUMMARY, FLOOD_ACK, REACH, UNREACH}
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
    # Flooding (self-pruning)
    covered: List[int]      # vizinhos de quem transmitiu (já ouviram esta transmissão)
    # GeoCast
    dest_pos: Position      # posição prevista do destino pelo plano compartilhado
    mode: str               # "greedy" (a caminho) ou "zone" (inundação na zona-alvo)


class BundleMessage(TypedDict):
    msg_type: str
    sender_id: int
    messages: List[DataMessage]


class SummaryMessage(TypedDict):
    msg_type: str
    sender_id: int
    ids: List[str]          # mensagens no meu buffer
    delivered: List[str]    # avisos de entrega: mensagens que sei que já foram entregues


class ReachMessage(TypedDict):
    msg_type: str
    sender_id: int
    endpoint: int
    seq: int                # nº do handshake do endpoint (descarta anúncios velhos)
