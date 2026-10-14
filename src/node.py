"""
Nó do cenário Swarm Core: enlace, mobilidade e agenda de tráfego (sem roteamento).

Camada comum a todos os protocolos (não entra nas métricas de roteamento):
- Beacons de enlace: cada nó anuncia id, papel, posição e (no
  Core) o ângulo da formação. Só os vizinhos dentro do alcance ouvem.
- Formação em cascata pela árvore: o ápice C1 voa o circuito do plano; cada
  outro nó segue o seu pai na árvore (FORMATION_PARENT) com o deslocamento do
  V, usando só o beacon do pai (posição e ângulo). O atraso do beacon é
  compensado pela lei de rotação do plano (centro e ω), não por velocidade
  medida — extrapolar velocidade amplificava o erro ao longo da cascata.
- Satélites: patrulham o setor; quando o plano prevê a passagem do seu lado,
  aproximam-se, escolhem o hub entre os nós do Core que ouvem (o próprio lado,
  se ouvido; senão o mais próximo) e confirmam por handshake (link_req/ack).
  Ficam em tandem sobre o hub por T a 4T s e se despedem (link_bye).
- BS: endpoint fixo; faz o mesmo handshake com o nó do Core mais próximo que ouve.

Ganchos para o roteamento: `_on_traffic`, `_on_packet`, `_on_contact`,
`_on_link_up/_on_link_down` (Core) e `_on_hub` (endpoints).
"""
import json
import random
from math import dist, radians
from typing import Dict, Optional

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.config import (
    APPROACH_LEAD, CORE_SPEED, HANDSHAKE_WAIT, LINK_BEACON, LINK_TIMEOUT, MOBILITY_SEED,
    PATROL_ARC, PATROL_RADIAL, ROTATION_OMEGA, SATELLITE_ALT, SATELLITE_SECTORS,
    SATELLITE_SPEED, TANDEM_T,
)
from src import eventlog, scenario as sc

CORE_STEP = 0.1               # s entre comandos de mobilidade do Core
SATELLITE_STEP = 0.2


class Neighbor:
    __slots__ = ("role", "position", "angle", "heard_at")

    def __init__(self, raw: dict, now: float):
        self.role = raw["role"]
        self.position = tuple(raw["pos"])
        self.angle = raw.get("angle")
        self.heard_at = now

    def predicted(self, t: float) -> sc.Position:
        """Posição em t: um nó do Core gira rigidamente com a formação (lei do
        plano); os demais ficam onde foram ouvidos."""
        if self.role != "core":
            return self.position
        return sc.rotate(self.position, ROTATION_OMEGA * (t - self.heard_at))


class SwarmNode(IProtocol):

    def initialize(self) -> None:
        self.node_id = self.provider.get_id()
        self.role = sc.role(self.node_id)
        self._position: sc.Position = sc.initial_position(self.node_id)
        self._rng = random.Random(MOBILITY_SEED * 1000 + self.node_id)
        self._links: Dict[int, Neighbor] = {}
        self._angle: Optional[float] = sc.formation_angle(0.0) if self.role == "core" else None

        # Endpoints (satélites e BS)
        self.hub: Optional[int] = None
        self._link_seq = 0
        self.flight = "fixo" if self.role == "bs" else "formação"
        # Core
        self.tethered: Dict[int, int] = {}  # endpoint → seq do handshake

        if self.role == "satellite":
            self._side = sc.satellite_side(self.node_id)
            self._sector = radians(SATELLITE_SECTORS[self.node_id][0])
            self._enter_patrol(0.0)
            self.provider.send_mobility_command(SetSpeedMobilityCommand(SATELLITE_SPEED))
            self.provider.schedule_timer("move", SATELLITE_STEP)
        elif self.role == "core":
            self.provider.schedule_timer("move", CORE_STEP)

        self.provider.schedule_timer("link_beacon", 0.01 * self.node_id)
        for index, (t, src, dst, name) in enumerate(sc.traffic()):
            if src == self.node_id:
                self.provider.schedule_timer(f"send:{index}", t)

    # ── Ganchos do roteamento ─────────────────────────────────────────────

    def _on_traffic(self, destination: int, name: str) -> None:
        pass

    def _on_packet(self, raw: dict) -> None:
        pass

    def _on_contact(self, peer: int) -> None:
        """Um vizinho passou a ser ouvido."""

    def _on_link_up(self, endpoint: int, seq: int) -> None:
        """(Core) Um endpoint fez handshake com este nó."""

    def _on_link_down(self, endpoint: int, seq: int) -> None:
        """(Core) Um endpoint ligado a este nó se despediu ou sumiu."""

    def _on_hub(self, hub: Optional[int]) -> None:
        """(Endpoint) O hub mudou (None = desconectado do Core)."""

    # ── Log ───────────────────────────────────────────────────────────────

    def _log(self, text: str) -> str:
        line = f"[{self.provider.current_time():6.1f}s][{sc.label(self.node_id):>3}] {text}"
        eventlog.write(line)
        return line

    # ── Vizinhança ────────────────────────────────────────────────────────

    def _alive(self, peer: int) -> bool:
        entry = self._links.get(peer)
        return entry is not None and self.provider.current_time() - entry.heard_at <= LINK_TIMEOUT

    def neighbors(self) -> Dict[int, Neighbor]:
        return {p: n for p, n in self._links.items() if self._alive(p)}

    def _send_raw(self, payload: dict, destination: Optional[int] = None) -> None:
        message = json.dumps(payload)
        if destination is None:
            self.provider.send_communication_command(BroadcastMessageCommand(message))
        else:
            self.provider.send_communication_command(SendMessageCommand(message, destination))

    def _link_beacon(self) -> None:
        now = self.provider.current_time()
        payload = {"msg_type": "link", "id": self.node_id, "role": self.role, "pos": self._position}
        if self.role == "core":
            payload["angle"] = self._current_angle(now)
        self._send_raw(payload)

        if self.role == "core":
            for endpoint, seq in list(self.tethered.items()):
                if not self._alive(endpoint):  # sumiu sem se despedir
                    del self.tethered[endpoint]
                    self._on_link_down(endpoint, seq)
        elif self.hub is not None and not self._alive(self.hub):
            self._set_hub(None)
        if self.role == "bs" and self.hub is None:
            self._request_link(self._choose_hub())

    # ── Handshake ─────────────────────────────────────────────────────────

    def _choose_hub(self) -> Optional[int]:
        core = {p: n for p, n in self.neighbors().items() if n.role == "core"}
        if not core:
            return None
        if self.role == "satellite" and self._side in core:
            return self._side
        return min(core, key=lambda p: dist(core[p].position, self._position))

    def _request_link(self, core: Optional[int]) -> None:
        if core is None:
            return
        self._link_seq += 1
        self._send_raw({"msg_type": "link_req", "id": self.node_id, "role": self.role,
                        "pos": self._position, "seq": self._link_seq}, core)

    def _set_hub(self, hub: Optional[int]) -> None:
        if hub == self.hub:
            return
        self._log(f"Conectou ao hub {sc.label(hub)}" if hub is not None
                  else f"Desconectou do hub {sc.label(self.hub)}")
        self.hub = hub
        self._on_hub(hub)

    def _handle_link(self, raw: dict) -> None:
        now = self.provider.current_time()
        kind, sender = raw["msg_type"], raw["id"]
        if kind == "link":
            fresh = not self._alive(sender)
            self._links[sender] = Neighbor(raw, now)
            if fresh:
                self._on_contact(sender)
        elif kind == "link_req" and self.role == "core":
            self._links[sender] = Neighbor(raw, now)  # o pedido também prova que o ouvi
            self.tethered[sender] = raw["seq"]
            self._send_raw({"msg_type": "link_ack", "id": self.node_id}, sender)
            self._on_link_up(sender, raw["seq"])
        elif kind == "link_bye" and self.role == "core":
            if self.tethered.get(sender) == raw["seq"]:
                del self.tethered[sender]
                self._on_link_down(sender, raw["seq"])
        elif kind == "link_ack" and self.role != "core":
            if self.role == "satellite" and self.flight == "handshake":
                self.flight = "tandem"
                self._tandem_end = now + self._rng.uniform(TANDEM_T, 4 * TANDEM_T)
            self._set_hub(sender)

    # ── Mobilidade do Core (cascata líder/seguidor) ───────────────────────

    def _current_angle(self, now: float) -> float:
        parent = sc.FORMATION_PARENT.get(self.node_id)
        if parent is None:
            return sc.formation_angle(now)
        entry = self._links.get(parent)
        if entry is not None and entry.angle is not None:
            self._angle = entry.angle + ROTATION_OMEGA * (now - entry.heard_at)
        return self._angle

    def _core_target(self, t: float) -> Optional[sc.Position]:
        parent = sc.FORMATION_PARENT.get(self.node_id)
        if parent is None:  # líder: voa o circuito do plano
            return sc.slot_position(self.node_id, t)
        if not self._alive(parent):  # sem pai: mantém a posição
            return None
        entry = self._links[parent]
        px, py, pz = entry.predicted(t)
        angle = entry.angle + ROTATION_OMEGA * (t - entry.heard_at)
        dx, dy = sc.slot_offset(self.node_id, parent, angle)
        return (px + dx, py + dy, pz)

    # ── Mobilidade dos satélites ──────────────────────────────────────────

    def _enter_patrol(self, now: float) -> None:
        self.flight = "patrulha"
        self._waypoint = None
        self._pass_at = sc.next_pass(self._side, self._sector, now + 1.0)

    def _satellite_target(self, now: float) -> sc.Position:
        if self.flight == "patrulha":
            if now >= self._pass_at - APPROACH_LEAD:
                self.flight = "aproximação"
            else:
                if self._waypoint is None or dist(self._waypoint, self._position) < 0.5:
                    self._waypoint = sc.satellite_home(
                        self.node_id,
                        self._rng.uniform(-PATROL_ARC, PATROL_ARC),
                        self._rng.uniform(-PATROL_RADIAL, PATROL_RADIAL),
                    )
                return self._waypoint

        if self.flight in ("aproximação", "handshake"):
            if now > self._pass_at + APPROACH_LEAD:  # perdeu a passagem: tenta na próxima
                self._enter_patrol(now)
                return self._position
            if self.flight == "aproximação" and any(n.role == "core" for n in self.neighbors().values()):
                self.flight = "handshake"
                self._handshake_at = now
            if self.flight == "handshake" and self.hub is None:
                side_heard = self._alive(self._side)
                if side_heard or now - self._handshake_at >= HANDSHAKE_WAIT:
                    self._request_link(self._choose_hub())  # reenvia até o ack chegar
            x, y, _ = sc.slot_position(self._side, max(now + SATELLITE_STEP, self._pass_at))
            return (x, y, SATELLITE_ALT)

        # tandem: acompanha o hub pelo beacon dele
        if now >= self._tandem_end or self.hub is None:
            if self.hub is not None:
                self._send_raw({"msg_type": "link_bye", "id": self.node_id, "seq": self._link_seq}, self.hub)
                self._set_hub(None)
            self._enter_patrol(now)
            return self._position
        x, y, _ = self._links[self.hub].predicted(now + SATELLITE_STEP)
        return (x, y, SATELLITE_ALT)

    # ── Handlers do GrADySim ──────────────────────────────────────────────

    def _goto(self, target: sc.Position, step: float, max_speed: float) -> None:
        speed = min(max_speed, max(dist(target, self._position) / step, 0.1))
        self.provider.send_mobility_command(SetSpeedMobilityCommand(speed))
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*target))

    def handle_timer(self, timer: str) -> None:
        now = self.provider.current_time()
        if timer == "link_beacon":
            self._link_beacon()
            self.provider.schedule_timer("link_beacon", now + LINK_BEACON[self.role])
        elif timer == "move":
            if self.role == "core":
                target = self._core_target(now + CORE_STEP)
                if target is not None:
                    self._goto(target, CORE_STEP, CORE_SPEED)
                self.provider.schedule_timer("move", now + CORE_STEP)
            else:
                target = self._satellite_target(now)
                speed = SATELLITE_SPEED if self.flight != "tandem" else CORE_SPEED
                self._goto(target, SATELLITE_STEP if self.flight == "tandem" else 1.0, speed)
                self.provider.schedule_timer("move", now + SATELLITE_STEP)
        elif timer.startswith("send:"):
            _, src, dst, name = sc.traffic()[int(timer.split(":")[1])]
            self._on_traffic(dst, name)

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        self._position = tuple(telemetry.current_position)

    def handle_packet(self, message: str) -> None:
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            return
        if raw.get("msg_type", "").startswith("link"):
            self._handle_link(raw)
        else:
            self._on_packet(raw)

    def finish(self) -> None:
        pass
