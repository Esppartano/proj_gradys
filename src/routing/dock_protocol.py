"""
Mensagens de acoplamento usadas pelo SwCore do professor (`swcore_professor.py`).

Os nomes são os do repositório original. No original, `get_sat` consulta um
registro global preenchido pelos satélites em tempo de execução; aqui ele lê
o plano compartilhado (cada eixo tem um satélite fixo, conhecido de antemão).
"""
from typing import Optional

from src.scenario import SAT_BY_REGION

MSG_DOCK_CONNECT = "dock_connect"
MSG_DOCK_DISCONNECT = "dock_disconnect"
MSG_DOCK_MSG_ACK = "dock_msg_ack"      # o hub confirma o upload do satélite
MSG_DOCK_DATA = "dock_data"            # upload: satélite → hub
MSG_DOCK_DELIVER = "dock_deliver"      # entrega: hub → satélite


def get_sat(face: str) -> Optional[int]:
    """Satélite do eixo `face` (N/E/S/W)."""
    return SAT_BY_REGION.get(face)
