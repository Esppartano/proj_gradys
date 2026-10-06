"""
Nó do cenário Swarm Core: mobilidade e agenda de tráfego, sem roteamento.

É a classe base sobre a qual os mixins de roteamento e visualização são
empilhados (mesmo padrão de extensão do template: mixins antes da base).

A mobilidade é roteiro do cenário (formação, ronda, órbitas, tandem) e usa o
relógio da simulação. O roteamento nunca usa o relógio para decidir caminhos.
"""
from typing import Dict, Optional

from gradysim.protocol.interface import IProtocol
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
from gradysim.protocol.messages.telemetry import Telemetry

from src.config import (
    CORE_SPEED, COVER_NODE, COVER_START, RONDA_END, RONDA_NODE, RONDA_RETURN,
    RONDA_START, RONDA_WAYPOINTS, SATELLITE_ALT, SATELLITE_PHASES,
    SIMULATION_DURATION, STEP_INTERVAL, TANDEM,
)
from src import scenario as sc

# Serviço de localização: última posição conhecida de cada nó (via telemetria).
# Usado apenas para preencher a posição do destino ao criar uma mensagem
# (premissa do GeoCast: a origem conhece a região de destino).
LOCATIONS: Dict[int, sc.Position] = {}


class SwarmNode(IProtocol):

    def initialize(self) -> None:
        self.node_id = self.provider.get_id()
        self.role = sc.role(self.node_id)
        self._position: sc.Position = sc.initial_position(self.node_id)
        LOCATIONS[self.node_id] = self._position
        self._orbit_phase: Optional[float] = SATELLITE_PHASES.get(self.node_id)
        self._was_tandem = False

        if self.role != "tower":
            self.provider.send_mobility_command(SetSpeedMobilityCommand(CORE_SPEED))
            self.provider.schedule_timer("move", self.provider.current_time())

        for index, (t, src, dst, name) in enumerate(sc.traffic()):
            if src == self.node_id:
                self.provider.schedule_timer(f"send:{index}", t)

    # ── Hook de tráfego (implementado pelo mixin de roteamento) ───────────

    def _on_traffic(self, destination: int, name: str) -> None:
        pass

    # ── Mobilidade ─────────────────────────────────────────────────────────

    def _target(self, t: float) -> sc.Position:
        if self.role == "core":
            if self.node_id == RONDA_NODE and RONDA_START <= t < RONDA_RETURN:
                _, x, y, z = [w for w in RONDA_WAYPOINTS if w[0] <= t][-1]
                return (x, y, z)
            if self.node_id == RONDA_NODE and RONDA_RETURN <= t < RONDA_END:
                return sc.slot_position(RONDA_NODE, RONDA_END)  # intercepta o slot
            return sc.slot_position(sc.core_slot(self.node_id, t), t)

        hub = self.tandem_hub(t)
        if hub is not None:
            self._was_tandem = True
            x, y, _ = sc.slot_position(sc.core_slot(hub, t), t)
            return (x, y, SATELLITE_ALT)
        if self._was_tandem:  # desacoplou: retoma a órbita a partir de onde está
            self._orbit_phase = sc.orbit_phase_at(self._position, t)
            self._was_tandem = False
        return sc.orbit_position(self._orbit_phase, t)

    def tandem_hub(self, t: float) -> Optional[int]:
        if self.node_id in TANDEM:
            hub, start, end = TANDEM[self.node_id]
            if start <= t < end:
                return hub
        return None

    def flight_state(self) -> str:
        """Descrição do estado de voo (HUD)."""
        t = self.provider.current_time()
        if self.role == "tower":
            return "Estação de solo fixa"
        if self.role == "satellite":
            hub = self.tandem_hub(t)
            return f"Voo tandem acoplado a {sc.label(hub)}" if hub else "Órbita periférica"
        if self.node_id == RONDA_NODE and RONDA_START <= t < RONDA_RETURN:
            return "Ronda externa (fora da formação)"
        if self.node_id == RONDA_NODE and RONDA_RETURN <= t < RONDA_END:
            return "Retornando ao slot na formação"
        if self.node_id == COVER_NODE and COVER_START <= t < RONDA_END:
            return f"Cobrindo a vaga de {sc.label(RONDA_NODE)} (FF Control)"
        return "Formação em V"

    # ── Handlers do GrADySim ───────────────────────────────────────────────

    def handle_timer(self, timer: str) -> None:
        now = self.provider.current_time()
        if timer == "move":
            x, y, z = self._target(now)
            self.provider.send_mobility_command(GotoCoordsMobilityCommand(x, y, z))
            if now + STEP_INTERVAL < SIMULATION_DURATION:
                self.provider.schedule_timer("move", now + STEP_INTERVAL)
        elif timer.startswith("send:"):
            _, src, dst, name = sc.traffic()[int(timer.split(":")[1])]
            self._on_traffic(dst, name)

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        self._position = tuple(telemetry.current_position)
        LOCATIONS[self.node_id] = self._position

    def handle_packet(self, message: str) -> None:
        pass

    def finish(self) -> None:
        pass
