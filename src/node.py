"""
Nó do cenário Swarm Core: enlace, mobilidade e geração de tráfego (sem roteamento).

Camada comum a todos os protocolos (não entra nas métricas de roteamento):
- Beacons de enlace: cada nó anuncia id, papel, posição e (no Core) o ângulo
  da formação. Só os vizinhos dentro do alcance ouvem.
- Formação em cascata pela árvore: o ápice C1 voa o circuito do plano; cada
  outro nó segue o seu pai na árvore (FORMATION_PARENT) com o deslocamento do
  V, usando só o beacon do pai (posição e ângulo). O atraso do beacon é
  compensado pela lei de rotação do plano (centro e ω), não por velocidade
  medida — extrapolar velocidade amplificava o erro ao longo da cascata.
- Satélites: esperam parados no ponto de acoplamento do seu eixo (5 m além do
  perímetro da formação). Descobrem os nós do Core pelo rádio (30 m) e acoplam
  no que passa pelo ponto (a até DOCK_CAPTURE m: uma das pontas do V),
  confirmando por handshake (link_req/ack). Acoplados, criam uma
  mensagem para o satélite do eixo oposto e trocam mensagens por
  CONTACT_DWELL s; depois se despedem (link_bye), afastam-se em linha reta
  pelo eixo, com velocidade constante, e voltam ao ponto de acoplamento.

Ganchos para o roteamento: `_on_traffic`, `_on_packet`, `_on_contact`,
`_on_link_up/_on_link_down` (Core) e `_on_hub` (satélites).
"""
import json
from math import dist
from typing import Dict, Optional

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.communication import BroadcastMessageCommand, SendMessageCommand
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.config import (
    CONTACT_DWELL, CONTACT_GAP, CORE_SPEED, DOCK_CAPTURE, LINK_BEACON, LINK_TIMEOUT, ROTATION_OMEGA,
    SATELLITE_PAIRS, SATELLITE_SPEED,
)
from src import config, eventlog, scenario as sc

CORE_STEP = 0.2               # s entre comandos de mobilidade do Core
SATELLITE_STEP = 0.2          # s entre decisões de mobilidade do satélite
ARRIVED = 0.5                 # m: considera que chegou ao ponto


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
        self._links: Dict[int, Neighbor] = {}
        self._angle: Optional[float] = sc.formation_angle(0.0) if self.role == "core" else None

        # Satélites
        self.hub: Optional[int] = None
        self._link_seq = 0      # último seq pedido
        self._acked_seq = 0     # seq confirmado pelo hub atual (usado no link_bye)
        self._last_contact = -CONTACT_GAP
        self._encounters = 0
        self._pending_message = False
        self._requested_hub: Optional[int] = None  # nó a quem pedi o acoplamento (ack ainda a caminho)
        self.flight = "formação"
        # Core
        self.tethered: Dict[int, int] = {}  # satélite → seq do handshake

        if self.role == "satellite":
            self.flight = "espera"
            self.provider.send_mobility_command(SetSpeedMobilityCommand(SATELLITE_SPEED))
            self.provider.schedule_timer("move", SATELLITE_STEP)
        else:
            self.provider.schedule_timer("move", CORE_STEP)
        self.provider.schedule_timer("link_beacon", 0.01 * self.node_id)

    # ── Ganchos do roteamento ─────────────────────────────────────────────

    def _on_traffic(self, destination: int, name: str) -> None:
        pass

    def _on_packet(self, raw: dict) -> None:
        pass

    def _on_contact(self, peer: int) -> None:
        """Um vizinho passou a ser ouvido."""

    def _on_link_up(self, endpoint: int, seq: int) -> None:
        """(Core) Um satélite fez handshake com este nó."""

    def _on_link_down(self, endpoint: int, seq: int) -> None:
        """(Core) Um satélite ligado a este nó se despediu ou sumiu."""

    def _on_hub(self, hub: Optional[int]) -> None:
        """(Satélite) O hub mudou (None = desconectado do Core)."""

    # ── Log ───────────────────────────────────────────────────────────────

    def _log(self, text: str) -> str:
        line = f"[{self.provider.current_time():7.1f}s][{sc.label(self.node_id):>3}] {text}"
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

    # ── Handshake ─────────────────────────────────────────────────────────

    def _choose_hub(self) -> Optional[int]:
        """O nó do Core que está passando pelo ponto de acoplamento: o mais
        próximo que este satélite ouve, se estiver a até DOCK_CAPTURE m."""
        core = {p: n for p, n in self.neighbors().items() if n.role == "core"}
        if not core:
            return None
        nearest = min(core, key=lambda p: dist(core[p].position, self._position))
        return nearest if dist(core[nearest].position, self._position) <= DOCK_CAPTURE else None

    def _request_link(self, core: Optional[int]) -> None:
        if core is None:
            return
        self._link_seq += 1
        self._requested_hub = core
        self._send_raw({"msg_type": "link_req", "id": self.node_id, "role": self.role,
                        "pos": self._position, "seq": self._link_seq}, core)

    def _set_hub(self, hub: Optional[int]) -> None:
        if hub == self.hub:
            return
        self._log(f"Conectou ao hub {sc.label(hub)}" if hub is not None
                  else f"Desconectou do hub {sc.label(self.hub)}")
        self.hub = hub
        self._requested_hub = None  # acoplamento confirmado ou encerrado: o pedido acabou
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
            self._send_raw({"msg_type": "link_ack", "id": self.node_id, "seq": raw["seq"]}, sender)
            self._on_link_up(sender, raw["seq"])
        elif kind == "link_bye" and self.role == "core":
            if self.tethered.get(sender) == raw["seq"]:
                del self.tethered[sender]
                self._on_link_down(sender, raw["seq"])
        elif kind == "link_ack" and self.role == "satellite":
            if self.hub is not None and sender != self.hub:  # ack de um pedido anterior a outro nó: desfaz
                self._send_raw({"msg_type": "link_bye", "id": self.node_id, "seq": raw["seq"]}, sender)
                return
            self._acked_seq = max(self._acked_seq, raw["seq"]) if sender == self.hub else raw["seq"]
            if self.flight == "espera":
                self._start_contact(now)
            self._set_hub(sender)
            if self.flight == "contato" and self._pending_message:
                self._pending_message = False
                self._create_message(now)

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

    # ── Satélites: espera → contato → afastamento → retorno ───────────────

    def _start_contact(self, now: float) -> None:
        self.flight = "contato"
        self._contact_end = now + CONTACT_DWELL
        self._last_contact = now
        self._pending_message = True  # criada assim que o hub estiver registrado
        self.provider.schedule_timer("undock", self._contact_end)  # desacopla exatamente após CONTACT_DWELL

    def _undock(self) -> None:
        """Fim da troca: despede-se do hub e começa a se afastar pelo eixo."""
        if self.hub is not None:
            self._send_raw({"msg_type": "link_bye", "id": self.node_id, "seq": self._acked_seq}, self.hub)
            self._set_hub(None)
        self.flight = "afastando"
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*sc.satellite_away(self.node_id)))

    def _create_message(self, now: float) -> None:
        """Cada acoplamento gera uma mensagem para o satélite do eixo oposto."""
        if now > config.TRAFFIC_END:  # lido na hora: o motor ajusta para a duração do modo 3D
            return
        self._encounters += 1
        destination = SATELLITE_PAIRS[self.node_id]
        self._on_traffic(destination, f"{sc.label(self.node_id)}>{sc.label(destination)}#{self._encounters}")

    def _satellite_target(self, now: float) -> sc.Position:
        dock = sc.satellite_dock(self.node_id)
        if self.flight == "espera":
            if dist(self._position, dock) <= ARRIVED and now - self._last_contact >= CONTACT_GAP:
                self._request_link(self._choose_hub())  # repete até o ack chegar
            return dock
        if self.flight == "contato":
            if self.hub is None:  # perdeu o hub antes do fim da troca
                self._undock()
            else:
                return dock
        if self.flight == "afastando":
            away = sc.satellite_away(self.node_id)
            if dist(self._position, away) <= ARRIVED:
                self.flight = "voltando"
                return dock
            return away
        # voltando
        if dist(self._position, dock) <= ARRIVED:
            self.flight = "espera"
            self._requested_hub = None
        return dock

    # ── Handlers do GrADySim ──────────────────────────────────────────────

    def _goto(self, target: sc.Position, step: float, max_speed: float) -> None:
        speed = min(max_speed, max(dist(target, self._position) / step, 0.01))
        self.provider.send_mobility_command(SetSpeedMobilityCommand(speed))
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*target))

    def handle_timer(self, timer: str) -> None:
        now = self.provider.current_time()
        if timer == "link_beacon":
            self._link_beacon()
            self.provider.schedule_timer("link_beacon", now + LINK_BEACON[self.role])
        elif timer == "undock":
            if self.flight == "contato" and now >= self._contact_end:
                self._undock()
        elif timer == "move":
            if self.role == "core":
                target = self._core_target(now + CORE_STEP)
                if target is not None:
                    self._goto(target, CORE_STEP, CORE_SPEED)
                self.provider.schedule_timer("move", now + CORE_STEP)
            else:
                # Velocidade constante, sempre em linha reta pelo eixo
                self.provider.send_mobility_command(GotoCoordsMobilityCommand(*self._satellite_target(now)))
                self.provider.schedule_timer("move", now + SATELLITE_STEP)

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
