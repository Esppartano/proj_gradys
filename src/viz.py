"""
Visualização: cores por papel e evento, variáveis no HUD e log de eventos.

O mixin só lê o estado exposto pelo nó e pelos protocolos; não altera nenhuma
decisão. Os comandos de visualização são reenviados a cada segundo porque o
GrADySim descarta os enviados antes de o navegador conectar.
"""
from gradysim.simulator.extension.visualization_controller import VisualizationController

from src.config import EVENT_HIGHLIGHT_S, EVENT_LOG, VIZ_NODE_SIZE
from src.scenario import BS, FORMATION_PARENT, label

PROTOCOL_NAMES = {"flooding": "Flooding", "geocast": "GeoCast", "dtn": "DTN", "swcore": "SwCore"}

# Cores por papel (RGB 0-255)
COLOR_BS = (20, 60, 220)           # azul: estação base
COLOR_APEX = (160, 32, 240)        # roxo: líder de mobilidade C1
COLOR_WING = (255, 255, 255)       # branco: asas do V
COLOR_SATELLITE = (255, 220, 0)    # amarelo: satélite em patrulha/aproximação
COLOR_TANDEM = (255, 140, 0)       # laranja: satélite em tandem
COLOR_CARRYING = (205, 133, 63)    # marrom-claro: carregando mensagens

# Cores de evento (duram EVENT_HIGHLIGHT_S segundos)
EVENT_COLORS = {
    "created": (255, 0, 200),      # magenta: criou mensagem
    "forwarded": (0, 255, 255),    # ciano: retransmitiu / repassou
    "handoff": (0, 255, 255),      # ciano: enviou lote de custódia (DTN)
    "pruned": (70, 70, 80),        # grafite: podou (GeoCast)
    "ttl_drop": (255, 20, 50),     # vermelho: descartou por TTL
    "delivered": (0, 255, 80),     # verde: recebeu mensagem destinada a ele
    "reach": (120, 255, 120),      # verde-claro: anunciou alcance (SwCore)
    "unreach": (255, 90, 90),      # vermelho-claro: anunciou perda (SwCore)
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

    def _log(self, text: str) -> str:
        line = super()._log(text)
        if EVENT_LOG:
            print(line)
        return line

    def _note(self, kind, text, stat=None, amount=1) -> None:
        super()._note(kind, text, stat, amount)
        self._repaint()

    def _set_hub(self, hub) -> None:
        super()._set_hub(hub)
        self._repaint()

    # ── Estado derivado ───────────────────────────────────────────────────

    def _role_color(self):
        if self.node_id == BS:
            return COLOR_BS
        if self.role == "satellite":
            return COLOR_TANDEM if self.flight == "tandem" else COLOR_SATELLITE
        return COLOR_APEX if self.node_id == 1 else COLOR_WING

    def _carrying(self) -> int:
        return (len(getattr(self, "_buffer", ())) + len(getattr(self, "_held", ()))
                + len(self._outbox))

    def _color(self):
        if self.last_event and self.provider.current_time() - self.last_event[2] <= EVENT_HIGHLIGHT_S:
            color = EVENT_COLORS.get(self.last_event[0])
            if color:
                return color
        if self._carrying() and self.node_id != BS:
            return COLOR_CARRYING
        return self._role_color()

    # ── Saída visual ──────────────────────────────────────────────────────

    def _repaint(self) -> None:
        self._vc.paint_node(self.node_id, self._color())
        self._vc.show_node_id(self.node_id, True)
        if self.node_id == BS:
            self._vc.resize_nodes(VIZ_NODE_SIZE)  # vale para todos os nós
        self._update_hud()

    def _update_hud(self) -> None:
        hud = self.provider.tracked_variables
        hud["Nó"] = label(self.node_id)
        hud["Protocolo"] = PROTOCOL_NAMES[self._protocol_name]
        if self.role == "core":
            parent = FORMATION_PARENT.get(self.node_id)
            hud["Formação"] = "líder (plano)" if parent is None else f"segue {label(parent)}"
            hud["Endpoints ligados"] = ", ".join(label(e) for e in self.tethered) or "-"
        else:
            hud["Estado"] = self.flight
            hud["Hub"] = label(self.hub) if self.hub is not None else "-"
        hud["Criadas / recebidas"] = f"{self.stats['created']} / {self.stats['received']}"
        hud["Carregando"] = self._carrying()
        if hasattr(self, "table") and self.role == "core":
            hud["Tabela"] = "; ".join(
                f"{label(e)}:{'direto' if r == 'direct' else ('-' if r is None else label(r))}"
                for e, (r, _) in sorted(self.table.items()))
        if self.last_event:
            _, text, at = self.last_event
            hud["Último evento"] = f"t={at:.1f}s: {text}"
