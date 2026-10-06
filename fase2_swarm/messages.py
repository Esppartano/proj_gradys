import json
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Tuple


class PacketType(str, Enum):
    DATA = "DATA"
    ACK = "ACK"
    BEACON = "BEACON"
    ROUTING = "ROUTING"


@dataclass
class Packet:
    packet_id: str
    source: int
    destination: int
    content: str
    packet_type: str = PacketType.DATA.value
    ttl: int = 10
    dest_pos: Optional[Tuple[float, float, float]] = None
    creation_time: float = 0.0
    hop_count: int = 0

    def serialize(self) -> str:
        data = asdict(self)
        return json.dumps(data)

    @staticmethod
    def deserialize(data: str) -> Optional["Packet"]:
        try:
            obj = json.loads(data)
            if obj.get("dest_pos") is not None:
                obj["dest_pos"] = tuple(obj["dest_pos"])
            return Packet(**obj)
        except Exception:
            return None