from typing import Tuple

from src.node import SwarmNode
from src.pubsub import PubSubCore, PubSubSatellite
from src.routing.dtn_mixin import DTNMixin
from src.routing.flooding_mixin import FloodingMixin
from src.routing.geocast_mixin import GeocastMixin
from src.routing.professor_adapter import ProfessorCoreAdapter, ProfessorSatelliteAdapter, RadioGate
from src.routing.swcore_mixin import SwCoreMixin
from src.routing.swcore_professor import SWCoreMixin as ProfessorSwCore
from src.viz import SwarmVizMixin

PROTOCOLS = {
    "flooding": FloodingMixin,
    "geocast": GeocastMixin,
    "dtn": DTNMixin,
    "swcore": SwCoreMixin,
}
# SwCore fornecido pelo professor: o mixin dele só vai nos nós do Core
PROFESSOR = {
    "core": (RadioGate, ProfessorSwCore, ProfessorCoreAdapter),
    "satellite": (RadioGate, ProfessorSatelliteAdapter),
}
# Pub/Sub (T2) sobre o SwCore do professor: a camada de pub/sub vem antes do roteamento
PUBSUB = {
    "core": (RadioGate, PubSubCore, ProfessorSwCore, ProfessorCoreAdapter),
    "satellite": (RadioGate, PubSubSatellite, ProfessorSatelliteAdapter),
}


def _mixins(protocol: str, role: str) -> Tuple[type, ...]:
    if protocol == "swcore_prof":
        return PROFESSOR[role]
    if protocol == "pubsub":
        return PUBSUB[role]
    return (PROTOCOLS[protocol],)


def make_node(protocol: str, viz: bool = False, role: str = "core") -> type:
    """
    Factory que combina os mixins de roteamento com o nó do cenário (mixins
    antes da classe base). Nos protocolos do T1 a classe é a mesma para os 13
    nós (o papel vem do ID); no SwCore do professor, Core e satélites usam
    classes diferentes (também no Pub/Sub, que roda sobre ele).
    """
    bases = _mixins(protocol, role) + (SwarmNode,)
    name = f"Node_{protocol}_{role}"
    if not viz:
        return type(name, bases, {})
    return type(name, (SwarmVizMixin,) + bases, {"_protocol_name": protocol})
