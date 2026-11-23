"""
SwCore fornecido pelo professor da disciplina (INF2541), reutilizado sem
alterar a lógica, como pede o enunciado do T2. Origem: repositório
github.com/INF2541-Intro-Mobile-Ubiquous-Computing/routing-ricardo, arquivo
src/swcore_mixin.py, commit 98392c1 (Ricardo Leta).

Mudanças em relação ao original (só integração): os imports de configuração,
de mensagens de acoplamento e de métricas apontam para os módulos deste
projeto. O que o código espera do nó (vizinhos com a tabela no beacon, fila
do Core, entrega ao satélite, eventos de acoplamento) é fornecido por
`src/routing/professor_adapter.py`.

Texto original:

SWCore mixin for core nodes — routing tables to satellites and core nodes.

Satellite RT (paper, Algorithm 1)
---------------------------------
- RT[Sx] is kept per *satellite*: ``direct`` (Sx is docked at this node), a
  next-hop core node, or ``unreachable`` (no entry counts as unreachable).
- ``connect(Sx)`` / ``disconnect(Sx)`` are triggered by the satellite's
  ``dock_connect`` / ``dock_disconnect`` and produce an RT-update that is
  flooded over every radio neighbour in the core.
- Every RT-update carries a version (origin time, origin id, counter) and the
  path it travelled (nodes to traverse to reach the node where Sx is direct).
  A node accepts only newer versions, which keeps the flood loop-free. Copies
  of the current version that arrive from other neighbours are kept as
  alternative paths: when the next hop stops beaconing (it failed), messages
  take the shortest alternative that is still alive.
- Messages for a satellite are forwarded along the table, delivered when the
  satellite is ``direct``, and otherwise kept in ``_core_buffer``; the buffer
  is retried periodically and whenever a ``reachable`` update arrives.
- The node where the sender is ``direct`` acknowledges each upload.
- A node that was cut off (see ``FailureMixin``) asks its neighbours for their
  RT rows when it comes back, to learn the updates it missed.

Core RT (path vector)
---------------------
Every core beacon carries the sender's best path to every other core node.
A node builds its own paths from the beacons of its *fresh* neighbours
(``[neighbour] + neighbour's path``, rejecting paths that contain itself) and
keeps the shortest. A failed node stops beaconing, drops out of the neighbour
tables after ``NEIGHBOR_TIMEOUT`` and the paths are rebuilt around it.
Triggered updates: whenever a node's paths change (a neighbour's beacon, or a
neighbour going stale, checked every ``SWCORE_RT_CHECK_INTERVAL``) it beacons
at once instead of waiting for the next periodic beacon.
``nearest_pspeer()`` gives the path to the closest PSPeer.

This mixin disables CoreDockMixin's delivery-on-alignment so that delivery only
happens through ``RT[Sy] == direct``.
"""
import json
import logging
from typing import Dict, List, Optional, Tuple

from gradysim.protocol.messages.communication import (
    BroadcastMessageCommand,
    SendMessageCommand,
)
from src.config import SWCORE_MAX_HOPS, SWCORE_RETRY_INTERVAL, SWCORE_RT_CHECK_INTERVAL
from src.routing.dock_protocol import (
    MSG_DOCK_CONNECT,
    MSG_DOCK_DISCONNECT,
    MSG_DOCK_MSG_ACK,
    get_sat,
)

DIRECT = "direct"
HOP = "hop"
UNREACHABLE = "unreachable"

MSG_RT_REQUEST = "swcore_rt_request"
RETRY_TIMER = "swcore_retry"
RT_CHECK_TIMER = "swcore_rt_check"

# Node ids of the PSPeers (filled by the pub/sub layer as each PSPeer starts).
PSPEER_IDS: List[int] = []


def build_core_paths(my_id: int, neighbour_rts: Dict[int, Dict[int, list]],
                     max_hops: int = SWCORE_MAX_HOPS) -> Dict[int, list]:
    """Shortest loop-free path to every core node from the neighbours' tables.

    ``neighbour_rts`` maps each fresh neighbour to the paths it advertised
    (destination → list of node ids, first hop first, destination last).
    Ties are broken by the lower neighbour id so the result is deterministic.
    """
    paths: Dict[int, list] = {nbr: [nbr] for nbr in neighbour_rts if nbr != my_id}
    for nbr in sorted(neighbour_rts):
        for dest, path in neighbour_rts[nbr].items():
            dest = int(dest)                       # JSON keys are strings
            if dest == my_id or my_id in path or nbr in path:
                continue
            cand = [nbr] + list(path)
            if len(cand) > max_hops:
                continue
            if dest not in paths or len(cand) < len(paths[dest]):
                paths[dest] = cand
    return paths


class SWCoreMixin:
    routing_msg_type = "routing_swcore"
    rt_msg_type = "swcore_rt"
    deliver_on_alignment = False   # read by CoreDockMixin

    _rt: Dict[int, dict]

    def initialize(self) -> None:
        if hasattr(super(), "initialize"):
            super().initialize()
        self._rt = {}
        self._ver_counter = 0
        self._paths_cache: Tuple[float, Dict[int, list]] = (-1.0, {})
        self._last_uses: Optional[frozenset] = None
        self._advertised: Optional[Dict[int, list]] = None
        self.provider.schedule_timer(
            RETRY_TIMER, self.provider.current_time() + SWCORE_RETRY_INTERVAL
        )
        self.provider.schedule_timer(
            RT_CHECK_TIMER, self.provider.current_time() + SWCORE_RT_CHECK_INTERVAL
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _new_ver(self) -> list:
        self._ver_counter += 1
        return [self.provider.current_time(), self.provider.get_id(), self._ver_counter]

    def _routing_neighbours(self) -> List[int]:
        """All core nodes currently in radio range (hub and ring links alike),
        so an update or a message can go around a failed node."""
        return list(self.fresh_neighbors())

    def _send(self, msg: dict, target: int) -> None:
        msg["sender_id"] = self.provider.get_id()
        self.provider.send_communication_command(
            SendMessageCommand(json.dumps(msg), target)
        )

    def _send_rt_update(self, sat: int, state: str, ver: list, exclude: Optional[int] = None) -> None:
        path = self._advertised_path(sat)
        for nid in self._routing_neighbours():
            if nid != exclude:
                self._send(
                    {"msg_type": self.rt_msg_type, "sat": sat, "state": state,
                     "ver": ver, "path": path},
                    nid,
                )

    def _advertised_path(self, sat: int) -> list:
        """Path a neighbour would take through this node to reach ``sat``."""
        row = self._rt.get(sat)
        my_id = self.provider.get_id()
        if row is None or row["state"] == UNREACHABLE:
            return []
        if row["state"] == DIRECT:
            return [my_id]
        return [my_id] + list(row["path"])

    def _buffered_for(self, sat: int) -> List[dict]:
        return [m for m in self._core_buffer.values() if m.get("dest_sat") == sat]

    def _forward(self, entry: dict, next_hop: int) -> bool:
        hops = entry.get("hops", 1) + 1
        if hops > SWCORE_MAX_HOPS:
            return False
        self._send({
            "msg_type": self.routing_msg_type,
            "id": entry["id"],
            "origin_face": entry.get("origin_face"),
            "dest_face": entry.get("dest_face"),
            "origin_sat": entry.get("origin_sat"),
            "dest_sat": entry.get("dest_sat"),
            "payload": entry.get("payload", {}),
            "created_at": entry.get("created_at", 0.0),
            "hops": hops,
            "next_hop": next_hop,
        }, next_hop)
        self._core_buffer.pop(entry["id"], None)  # custody moves to the next hop
        return True

    # ── Core RT (path vector) ─────────────────────────────────────────────

    def core_paths(self) -> Dict[int, list]:
        """Path (nodes to traverse, destination last) to every reachable core node."""
        now = self.provider.current_time()
        if self._paths_cache[0] != now:
            nbr_rts = {nid: data.get("rt") or {} for nid, data in self.fresh_neighbors().items()}
            self._paths_cache = (now, build_core_paths(self.provider.get_id(), nbr_rts))
        return self._paths_cache[1]

    def next_hop_core(self, dest: int) -> Optional[int]:
        path = self.core_paths().get(dest)
        return path[0] if path else None

    def nearest_pspeer(self) -> Tuple[Optional[int], list]:
        """(PSPeer id, path) of the closest PSPeer; (self, []) on a PSPeer."""
        my_id = self.provider.get_id()
        if my_id in PSPEER_IDS:
            return my_id, []
        paths = self.core_paths()
        best = [(len(paths[p]), p) for p in PSPEER_IDS if p in paths]
        if not best:
            return None, []
        _, peer = min(best)
        return peer, paths[peer]

    def beacon_extra(self) -> dict:
        """Added to every core beacon: this node's paths to the other core nodes.
        Also records which relays this node's routes currently use (metrics)."""
        paths = self.core_paths()
        self._advertised = paths
        self._record_route_usage(paths)
        return {"rt": {str(dest): path for dest, path in paths.items()}}

    def on_neighbors_changed(self) -> None:
        """Called by NeighborMixin after each core beacon."""
        self._paths_cache = (-1.0, {})
        self._trigger_if_changed()

    def _trigger_if_changed(self) -> None:
        """Triggered update: beacon now if the paths differ from the last ones
        advertised."""
        paths = self.core_paths()
        if self._advertised is not None and paths != self._advertised:
            self._send_beacon()
        else:
            self._record_route_usage(paths)

    def _sat_path(self, sat: int) -> Optional[list]:
        """Path the next message for ``sat`` would take (None: keep buffered).

        The RT-update says which core node the satellite is docked at (last
        node of the path); the core RT gives the shortest live path to that
        node. Without one, fall back to the update's next hop or the shortest
        live alternative."""
        row = self._rt.get(sat)
        if row is None or row["state"] != HOP:
            return None
        if row["path"]:
            core_path = self.core_paths().get(row["path"][-1])
            if core_path:
                return core_path
        fresh = self.fresh_neighbors()
        if row["next_hop"] in fresh:
            return row["path"]
        alts = [path for nbr, path in row.get("alts", {}).items() if nbr in fresh]
        return min(alts, key=len) if alts else None

    def _record_route_usage(self, paths: Dict[int, list]) -> None:
        """Relays this node depends on: the path to the nearest PSPeer, every
        intermediate node on its paths to core nodes, and the next hop towards
        each satellite (further hops are chosen by that next hop)."""
        if getattr(self, "_down", False):
            return
        uses = set(self.nearest_pspeer()[1])
        for path in paths.values():
            uses.update(path[:-1])
        for sat in self._rt:
            path = self._sat_path(sat)
            if path and len(path) > 1:
                uses.add(path[0])
        uses = frozenset(uses)
        if uses != self._last_uses:
            self._last_uses = uses
            from src.metrics import record_rt_snapshot
            record_rt_snapshot(self.provider.get_id(), self.provider.current_time(), uses)

    # ── Algorithm 1 ───────────────────────────────────────────────────────

    def _on_connect(self, sat: int, face: str) -> None:
        self._rt[sat] = {"state": DIRECT, "next_hop": None, "path": [], "alts": {},
                         "ver": self._new_ver()}
        logging.info(f"[SWCORE {self.provider.get_id()}] connect({sat}) RT[{sat}]=direct")
        self._send_rt_update(sat, "reachable", self._rt[sat]["ver"])
        pending = self._buffered_for(sat)
        if pending:
            self._deliver_to_sat(face, sat, pending)

    def _on_disconnect(self, sat: int) -> None:
        self._rt[sat] = {"state": UNREACHABLE, "next_hop": None, "path": [], "alts": {},
                         "ver": self._new_ver()}
        logging.info(f"[SWCORE {self.provider.get_id()}] disconnect({sat}) RT[{sat}]=unreachable")
        self._send_rt_update(sat, "unreachable", self._rt[sat]["ver"])

    def _on_rt_update(self, raw: dict) -> None:
        sat, sender, state = raw["sat"], raw["sender_id"], raw["state"]
        ver = list(raw["ver"])
        path = list(raw.get("path") or [sender])
        my_id = self.provider.get_id()
        cur = self._rt.get(sat)

        if cur is not None and ver == cur["ver"]:
            # Same update over another path: keep it as an alternative, or make
            # it the primary route if it is shorter (the flood's first copy may
            # have come the long way round).
            if (state == "reachable" and cur["state"] == HOP and sender != cur["next_hop"]
                    and my_id not in path):
                if len(path) < len(cur["path"]):
                    cur["alts"][cur["next_hop"]] = cur["path"]
                    cur["alts"].pop(sender, None)
                    cur["next_hop"], cur["path"] = sender, path
                else:
                    cur["alts"][sender] = path
            return
        if cur is not None and ver < cur["ver"]:
            return  # stale
        if state == "reachable":
            if my_id in path:
                return  # would loop through this node
            self._rt[sat] = {"state": HOP, "next_hop": sender, "path": path, "alts": {},
                             "ver": ver}
        else:
            self._rt[sat] = {"state": UNREACHABLE, "next_hop": None, "path": [], "alts": {},
                             "ver": ver}
        logging.info(
            f"[SWCORE {my_id}] RT[{sat}]={state} via {sender} path={path}"
        )
        self._send_rt_update(sat, state, ver, exclude=sender)
        if state == "reachable":
            for entry in self._buffered_for(sat):
                self._route(entry)

    def _route(self, entry: dict) -> None:
        """recv(message, Sx, Sy): deliver, forward or keep in the buffer."""
        sat = entry.get("dest_sat")
        row = self._rt.get(sat)
        if row is None or row["state"] == UNREACHABLE:
            return  # stays in _core_buffer
        if row["state"] == DIRECT:
            self._deliver_to_sat(entry["dest_face"], sat, [entry])
            return
        path = self._sat_path(sat)
        if path:
            self._forward(entry, path[0])
        # no live next hop: stays in _core_buffer until the retry timer

    def _ack_if_direct(self, entry: dict) -> None:
        origin = entry.get("origin_sat")
        row = self._rt.get(origin)
        if row is not None and row["state"] == DIRECT:
            self._send({"msg_type": MSG_DOCK_MSG_ACK, "id": entry["id"]}, origin)

    # ── Recovery after an outage ──────────────────────────────────────────

    def on_comm_restored(self) -> None:
        """Called by FailureMixin: ask the neighbours for the RT rows we missed."""
        self.provider.send_communication_command(BroadcastMessageCommand(json.dumps({
            "msg_type": MSG_RT_REQUEST, "sender_id": self.provider.get_id(),
        })))
        if hasattr(super(), "on_comm_restored"):
            super().on_comm_restored()

    def _answer_rt_request(self, requester: int) -> None:
        for sat, row in self._rt.items():
            state = "unreachable" if row["state"] == UNREACHABLE else "reachable"
            self._send(
                {"msg_type": self.rt_msg_type, "sat": sat, "state": state,
                 "ver": row["ver"], "path": self._advertised_path(sat)},
                requester,
            )

    # ── Hooks ─────────────────────────────────────────────────────────────

    def on_dock_upload(self, msg: dict) -> None:
        """Called by CoreDockMixin when a satellite uploads dock_data.

        (Not ``route_in_core``: CoreDockMixin precedes the strategy mixins in the
        MRO, so its no-op ``route_in_core`` shadows any override.)"""
        sat = msg.get("sender_id")
        row = self._rt.get(sat)
        if row is None or row["state"] != DIRECT:
            self._on_connect(sat, msg["origin_face"])  # connect not seen yet
        msg["origin_sat"] = sat
        msg["dest_sat"] = get_sat(msg["dest_face"])
        self._route(msg)
        self._ack_if_direct(msg)

    def handle_timer(self, timer: str) -> None:
        if timer == RT_CHECK_TIMER:
            self._paths_cache = (-1.0, {})   # a neighbour may have gone stale
            self._trigger_if_changed()
            self.provider.schedule_timer(
                RT_CHECK_TIMER, self.provider.current_time() + SWCORE_RT_CHECK_INTERVAL
            )
            return
        if timer == RETRY_TIMER:
            for entry in list(self._core_buffer.values()):
                row = self._rt.get(entry.get("dest_sat"))
                if row is not None and row["state"] == HOP:
                    self._route(entry)
            self.provider.schedule_timer(
                RETRY_TIMER, self.provider.current_time() + SWCORE_RETRY_INTERVAL
            )
            return
        if hasattr(super(), "handle_timer"):
            super().handle_timer(timer)

    def handle_packet(self, message: str) -> None:
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            if hasattr(super(), "handle_packet"):
                super().handle_packet(message)
            return

        msg_type = raw.get("msg_type")

        if msg_type == MSG_DOCK_CONNECT:
            self._on_connect(raw["sender_id"], raw["face"])
            return
        if msg_type == MSG_DOCK_DISCONNECT:
            self._on_disconnect(raw["sender_id"])
            return
        if msg_type == self.rt_msg_type:
            self._on_rt_update(raw)
            return
        if msg_type == MSG_RT_REQUEST:
            self._answer_rt_request(raw["sender_id"])
            return
        if msg_type == self.routing_msg_type:
            if raw.get("next_hop") != self.provider.get_id() or not raw.get("id"):
                return
            entry = {k: raw.get(k) for k in (
                "id", "origin_face", "dest_face", "origin_sat", "dest_sat",
                "payload", "created_at", "hops",
            )}
            self._core_buffer[entry["id"]] = entry
            self._route(entry)
            self._ack_if_direct(entry)
            return

        if hasattr(super(), "handle_packet"):
            super().handle_packet(message)

    def finish(self) -> None:
        if hasattr(super(), "finish"):
            super().finish()
