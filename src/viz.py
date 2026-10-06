"""
Visualização: cores por papel e evento, variáveis no HUD e log de eventos.

O mixin só lê o estado exposto pelo nó (`flight_state`) e pelos protocolos
(`stats`, `last_event`, buffers); não altera nenhuma decisão de roteamento.
Os comandos de visualização são reenviados a cada segundo porque o GrADySim
descarta os enviados antes de o navegador conectar.
"""
from gradysim.simulator.extension.visualization_controller import VisualizationController

from src.config import (
    COVER_NODE, COVER_START, EVENT_HIGHLIGHT_S, EVENT_LOG, RONDA_END, RONDA_NODE,
    RONDA_START, VIZ_NODE_SIZE,
)
from src.scenario import TOWER, label

PROTOCOL_NAMES = {"flooding": "Flooding", "geocast": "GeoCast", "dtn": "DTN", "tree": "Árvore Geradora"}

# Cores por papel (RGB 0-255), as mesmas do Swarm Core original
COLOR_TOWER = (20, 60, 220)        # azul royal: torre terrestre
COLOR_APEX = (160, 32, 240)        # roxo: líder C1
COLOR_WING = (30, 144, 255)        # azul claro: asas do V
COLOR_COVER = (0, 190, 255)        # turquesa: nó cobrindo a vaga (FF Control)
COLOR_RONDA = (255, 140, 0)        # laranja: nó em ronda externa
COLOR_SATELLITE = (255, 220, 0)    # amarelo: satélites
COLOR_CARRYING = (205, 133, 63)    # marrom-claro: carregando mensagens (DTN / Árvore)

# Cores de evento (duram EVENT_HIGHLIGHT_S segundos)
EVENT_COLORS = {
    "created": (255, 0, 200),      # magenta: criou mensagem
    "forwarded": (0, 255, 255),    # ciano: retransmitiu / repassou
    "handoff": (0, 255, 255),      # ciano: enviou lote de custódia (DTN)
    "acked": (255, 255, 255),      # branco: custódia confirmada (DTN)
    "pruned": (70, 70, 80),        # grafite: podou (GeoCast)
    "ttl_drop": (255, 20, 50),     # vermelho: descartou por TTL
    "delivered": (0, 255, 80),     # verde: recebeu mensagem destinada a ele
}

ROLE_NAMES = {
    TOWER: "Torre Terrestre / Estação Base",
    1: "Core Ápice Líder",
}


class SwarmVizMixin:

    _protocol_name: str = ""

    def initialize(self) -> None:
        super().initialize()
        self._vc = VisualizationController(self)
        self._repaint()
        self.provider.schedule_timer("repaint", self.provider.current_time() + 1)

    def handle_timer(self, timer: str) -> None:
        super().handle_timer(timer)
        if timer == "repaint":
            self._repaint()
            self.provider.schedule_timer("repaint", self.provider.current_time() + 1)

    def _note(self, kind, text, stat=None, amount=1) -> None:
        super()._note(kind, text, stat, amount)
        if EVENT_LOG:
            now = self.provider.current_time()
            print(f"[{now:5.1f}s][{label(self.provider.get_id()):>5}] {text}")
        self._repaint()  # mostra a cor do evento na hora

    # ── Estado derivado ───────────────────────────────────────────────────

    def _role_color(self):
        node_id, t = self.provider.get_id(), self.provider.current_time()
        if node_id == TOWER:
            return COLOR_TOWER
        if self.role == "satellite":
            return COLOR_SATELLITE
        if node_id == RONDA_NODE and RONDA_START <= t < RONDA_END:
            return COLOR_RONDA
        if node_id == COVER_NODE and COVER_START <= t < RONDA_END:
            return COLOR_COVER
        return COLOR_APEX if node_id == 1 else COLOR_WING

    def _carrying(self) -> int:
        return len(getattr(self, "_buffer", ())) + len(getattr(self, "_pending", ())) + len(getattr(self, "_hold", ()))

    def _color(self):
        if self.last_event and self.provider.current_time() - self.last_event[2] <= EVENT_HIGHLIGHT_S:
            color = EVENT_COLORS.get(self.last_event[0])
            if color:
                return color
        if self._carrying() and self.role != "tower":
            return COLOR_CARRYING
        return self._role_color()

    # ── Saída visual ──────────────────────────────────────────────────────

    def _repaint(self) -> None:
        node_id = self.provider.get_id()
        self._vc.paint_node(node_id, self._color())
        self._vc.show_node_id(node_id, True)
        if node_id == TOWER:
            self._vc.resize_nodes(VIZ_NODE_SIZE)  # vale para todos os nós
        self._update_hud()

    def _update_hud(self) -> None:
        node_id = self.provider.get_id()
        hud = self.provider.tracked_variables
        name = ROLE_NAMES.get(node_id)
        if name is None:
            if self.role == "satellite":
                name = "Satélite Periférico"
            else:
                name = "Core Asa Esquerda" if node_id <= 5 else "Core Asa Direita"
        hud["Papel"] = f"{name} ({label(node_id)})"
        hud["Protocolo"] = PROTOCOL_NAMES[self._protocol_name]
        hud["Estado"] = self.flight_state()
        if hasattr(self, "effective_parent") and node_id != TOWER and self.role == "core":
            parent = self.effective_parent()
            hud["Topologia"] = f"Pai na árvore: {label(parent) if parent is not None else 'nenhum (aguardando)'}"
        hud["Mensagens criadas / recebidas"] = f"{self.stats['created']} / {self.stats['received']}"
        if self._protocol_name in ("flooding", "geocast"):
            hud["Retransmissões"] = self.stats["forwarded"]
            hud["Recepções redundantes"] = self.stats["redundant"]
            if self._protocol_name == "geocast":
                hud["Podas (fora da zona)"] = self.stats["pruned"]
        elif self._protocol_name == "dtn":
            hud["Buffer DTN"] = f"{len(self._buffer)} msg(s) ({len(self._in_transfer)} aguardando ACK)"
            hud["Custódia enviada / recebida"] = f"{self.stats['handed_off']} / {self.stats['custody']}"
        else:
            hud["Repasses na árvore"] = self.stats["forwarded"]
            hud["Aguardando próximo salto / cópias guardadas"] = f"{len(self._pending)} / {len(self._hold)}"
        if self.last_event:
            _, text, at = self.last_event
            hud["Último evento"] = f"t={at:.1f}s: {text}"
