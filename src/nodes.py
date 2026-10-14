from src.node import SwarmNode
from src.routing.dtn_mixin import DTNMixin
from src.routing.flooding_mixin import FloodingMixin
from src.routing.geocast_mixin import GeocastMixin
from src.routing.swcore_mixin import SwCoreMixin
from src.viz import SwarmVizMixin

PROTOCOLS = {
    "flooding": FloodingMixin,
    "geocast": GeocastMixin,
    "dtn": DTNMixin,
    "swcore": SwCoreMixin,
}


def make_node(protocol: str, viz: bool = False) -> type:
    """
    Factory que combina o mixin de roteamento escolhido com o nó do cenário
    (mixins antes da classe base). Todos os 14 nós usam a mesma classe; o
    papel vem do ID.
    """
    RoutingMixin = PROTOCOLS[protocol]
    if not viz:
        return type(f"Node_{protocol}", (RoutingMixin, SwarmNode), {})
    return type(f"Node_{protocol}", (SwarmVizMixin, RoutingMixin, SwarmNode), {"_protocol_name": protocol})
