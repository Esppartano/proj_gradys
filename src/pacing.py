"""
Ritmo do modo 3D: roda a simulação VIZ_SPEEDUP vezes mais rápido que o tempo real.

O `real_time` do GrADySim espera um pouco antes de cada evento, e essas esperas
relativas acumulam atraso: pedindo 30×, medimos só ≈ 5×. Este handler usa
prazos absolutos: a cada passo, o instante simulado t deve acontecer em
`início + t / fator` no relógio; se a simulação está adiantada, dorme até lá.
"""
import time

from gradysim.simulator.event import EventLoop
from gradysim.simulator.handler.interface import INodeHandler
from gradysim.simulator.node import Node

TICK = 0.05  # s reais entre verificações do ritmo


class PacingHandler(INodeHandler):

    def __init__(self, speedup: float):
        self._speedup = speedup
        self._step = TICK * speedup  # s simulados entre verificações
        self._loop = None
        self._start = 0.0

    @staticmethod
    def get_label() -> str:
        return "pacing"

    def inject(self, event_loop: EventLoop) -> None:
        self._loop = event_loop

    def register_node(self, node: Node) -> None:
        pass

    def initialize(self) -> None:
        self._start = time.perf_counter()
        self._loop.schedule_event(self._loop.current_time, self._tick, "pacing")

    def _tick(self) -> None:
        now = self._loop.current_time
        delay = self._start + now / self._speedup - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        self._loop.schedule_event(now + self._step, self._tick, "pacing")
