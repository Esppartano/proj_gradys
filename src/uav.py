from typing import List, Tuple

from utils.actor_templates.uav_template import make_uav_protocol
from utils.viz_templates.uav_viz_template import UAVVizMixin

from src.routing.dtn_mixin import DTNMixin
from src.routing.flooding_mixin import FloodingMixin
from src.routing.geocast_mixin import GeocastMixin

PROTOCOLS = {
    "flooding": FloodingMixin,
    "geocast": GeocastMixin,
    "dtn": DTNMixin,
}


def make_uav(
    protocol: str,
    waypoints: List[Tuple[float, float, float]],
    departure_delay: float = 0.0,
    viz: bool = False,
) -> type:
    """
    Factory que combina o mixin de roteamento escolhido com a UAV do template.

    Cada UAV voa sozinha na sua rota (num_uavs=1, sem offset de formação);
    o espalhamento ao longo da rota vem do `departure_delay`.
    """
    RoutingMixin = PROTOCOLS[protocol]
    Base = make_uav_protocol(
        waypoints=waypoints,
        cluster_index=0,
        num_uavs=1,
        departure_delay=departure_delay,
    )
    bases = (UAVVizMixin, RoutingMixin, Base) if viz else (RoutingMixin, Base)
    return type(f"UAV_{protocol}", bases, {})
