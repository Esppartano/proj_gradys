from src.node import SwarmNode
from src.routing.dtn_mixin import DTNMixin
from src.routing.flooding_mixin import FloodingMixin
from src.routing.geocast_mixin import GeocastMixin
from src.routing.tree_mixin import TreeMixin
from src.viz import SwarmVizMixin

PROTOCOLS = {
    "flooding": FloodingMixin,
    "geocast": GeocastMixin,
    "dtn": DTNMixin,
    "tree": TreeMixin,
}


def make_node(protocol: str, viz: bool = False) -> type:
    """
    Factory que combina o mixin de roteamento escolhido com o nó do cenário
    (mesmo padrão de extensão do template: mixins antes da classe base).
    Todos os 14 nós usam a mesma classe; o papel vem do ID.
    """
    RoutingMixin = PROTOCOLS[protocol]
    if not viz:
        return type(f"Node_{protocol}", (RoutingMixin, SwarmNode), {})
    return type(f"Node_{protocol}", (SwarmVizMixin, RoutingMixin, SwarmNode), {"_protocol_name": protocol})
