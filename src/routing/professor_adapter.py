"""
Integração do SwCore do professor (`swcore_professor.py`) com o nó deste projeto.

O SwCore do professor é um mixin para os nós do Core e espera do nó:
- `fresh_neighbors()`: vizinhos do Core ouvidos há até NEIGHBOR_TIMEOUT s,
  cada um com os caminhos (`rt`) que anunciou no beacon;
- `_send_beacon()` e o gancho `beacon_extra()`: os caminhos vão no beacon de
  enlace, e uma mudança de caminhos dispara um beacon na hora;
- `_core_buffer` e `_deliver_to_sat()`: a fila do Core e a entrega ao satélite
  acoplado;
- `_on_connect` / `_on_disconnect` / `on_dock_upload`: chamados aqui a partir
  do handshake de acoplamento já existente (link_req/link_bye) e do upload do
  satélite;
- `on_comm_restored()`: chamado pelo nó no fim da falha.

Do lado do satélite (sem o mixin do professor), segue o comportamento do
SwCore original: o satélite entrega cada mensagem ao hub e a mantém até a
confirmação (`dock_msg_ack`); sem confirmação, reenvia no próximo acoplamento.

A lista de PSPeers do SwCore vem do plano compartilhado (`scenario.PSPEERS`).
"""
import json
from typing import Dict, Optional

from gradysim.protocol.messages.communication import SendMessageCommand

from src.config import NEIGHBOR_TIMEOUT
from src.metrics import METRICS
from src.routing import messages as m
from src.routing import swcore_professor as sw
from src.routing.base import RoutingMixin
from src.routing.dock_protocol import MSG_DOCK_DATA, MSG_DOCK_DELIVER, MSG_DOCK_MSG_ACK
from src import scenario
from src.scenario import label, region, role

DATA_TYPES = {sw.SWCoreMixin.routing_msg_type, MSG_DOCK_DATA, MSG_DOCK_DELIVER, m.PUBSUB}
CONTROL_TYPES = {sw.SWCoreMixin.rt_msg_type, sw.MSG_RT_REQUEST, MSG_DOCK_MSG_ACK}


class RadioGate:
    """Primeiro na MRO: durante a falha o nó não recebe nada (nem o código do
    professor); fora dela, conta a recepção de pacotes de roteamento."""

    def handle_packet(self, message: str) -> None:
        if self.radio_down:
            return
        try:
            kind = json.loads(message).get("msg_type", "")
        except json.JSONDecodeError:
            return
        if kind in DATA_TYPES or kind in CONTROL_TYPES:
            METRICS.rx += 1
        super().handle_packet(message)


class ProfessorAdapterBase(RoutingMixin):
    """Comum a Core e satélites: contagem de transmissões do SwCore do professor."""

    def _on_transmit(self, command) -> None:
        try:
            kind = json.loads(command.message).get("msg_type", "")
        except json.JSONDecodeError:
            return
        if kind in DATA_TYPES:
            METRICS.data_tx += 1
            METRICS.data_msgs_tx += 1
        elif kind in CONTROL_TYPES:
            METRICS.control_tx += 1

    def _on_routing(self, raw: dict) -> None:
        pass  # nada passa pelos tipos de roteamento do T1


class ProfessorCoreAdapter(ProfessorAdapterBase):
    """Vem depois de `swcore_professor.SWCoreMixin` na MRO do nó do Core."""

    def initialize(self) -> None:
        super().initialize()
        self._core_buffer: Dict[str, dict] = {}
        sw.PSPEER_IDS[:] = list(scenario.PSPEERS)  # plano compartilhado; preenchido ao iniciar cada nó do Core

    # ── O que o SwCore do professor espera do nó ──────────────────────────

    @property
    def _down(self) -> bool:
        return self.radio_down

    def fresh_neighbors(self) -> Dict[int, dict]:
        now = self.provider.current_time()
        return {p: {"rt": n.rt, "position": n.position, "role": n.role, "last_seen": n.heard_at}
                for p, n in self._links.items()
                if n.role == "core" and now - n.heard_at <= NEIGHBOR_TIMEOUT}

    def _deliver_to_sat(self, face: str, sat_id: int, messages: list) -> None:
        for msg in messages:
            if not msg.get("id"):
                continue
            self.provider.send_communication_command(SendMessageCommand(json.dumps({
                "msg_type": MSG_DOCK_DELIVER, "id": msg["id"], "origin_face": msg.get("origin_face"),
                "dest_face": face, "payload": msg.get("payload", {}), "created_at": msg.get("created_at", 0.0),
                "hops": msg.get("hops", 1) + 1, "sender_id": self.node_id,
            }), sat_id))
            self._core_buffer.pop(msg["id"], None)
            name = (msg.get("payload") or {}).get("name", msg["id"])
            self._note("forwarded", f"Entregou {name} direto a {label(sat_id)}", "forwarded")

    # ── Acoplamento (handshake do nó) → eventos do SwCore ─────────────────

    def _on_link_up(self, endpoint: int, seq: int) -> None:
        super()._on_link_up(endpoint, seq)
        self._on_connect(endpoint, region(endpoint))
        self._note("reach", f"{label(endpoint)} conectou: anunciou alcance")

    def _on_link_down(self, endpoint: int, seq: int) -> None:
        super()._on_link_down(endpoint, seq)
        self._on_disconnect(endpoint)
        self._note("unreach", f"{label(endpoint)} desconectou: anunciou perda")

    def _on_packet(self, raw: dict) -> None:
        if raw.get("msg_type") != MSG_DOCK_DATA or raw.get("sender_id") not in self.tethered:
            return
        entry = dict(raw, hops=1)  # como no original: o upload inteiro (inclui sender_id) vai para a fila
        self._core_buffer[entry["id"]] = entry
        self.on_dock_upload(entry)

    # ── Estado observável (HUD) ───────────────────────────────────────────

    @property
    def table(self) -> Dict[int, tuple]:
        """Rota para cada satélite, no formato que a visualização mostra:
        "direct", o próximo salto ou None (inalcançável)."""
        route = {sw.DIRECT: lambda row: "direct", sw.HOP: lambda row: row["next_hop"],
                 sw.UNREACHABLE: lambda row: None}
        return {sat: (route[row["state"]](row), 0) for sat, row in self._rt.items()}

    def _can_originate(self) -> bool:
        return True

    def _originate(self, message: m.DataMessage) -> None:
        pass  # no tráfego do T1 só os satélites criam mensagens


class ProfessorSatelliteAdapter(ProfessorAdapterBase):
    """Satélite: entrega ao hub e guarda até a confirmação."""

    def initialize(self) -> None:
        super().initialize()
        self._pending_uploads: Dict[str, dict] = {}  # id → upload ainda sem dock_msg_ack

    def _can_originate(self) -> bool:
        return self.hub is not None

    def _originate(self, message: m.DataMessage) -> None:
        upload = {
            "msg_type": MSG_DOCK_DATA, "id": message["message_id"], "origin_face": region(self.node_id),
            "dest_face": region(message["destination"]), "created_at": message["created_at"],
            "payload": {"name": message["name"]}, "sender_id": self.node_id,
        }
        self._pending_uploads[upload["id"]] = upload
        self._upload(upload)

    def _upload(self, upload: dict) -> None:
        self.provider.send_communication_command(SendMessageCommand(json.dumps(upload), self.hub))
        self._note("forwarded", f"Entregou {upload['payload']['name']} ao hub {label(self.hub)}", "forwarded")

    def _on_hub(self, hub: Optional[int]) -> None:
        if hub is not None:  # reenvia o que o hub anterior não confirmou
            for upload in list(self._pending_uploads.values()):
                self._upload(upload)
        super()._on_hub(hub)

    def _on_packet(self, raw: dict) -> None:
        # Como no satélite original: confirmação e entrega valem em qualquer estado (podem
        # chegar logo depois do link_bye, ainda ao alcance), desde que venham do Core.
        if role(raw.get("sender_id")) != "core":
            return
        kind = raw.get("msg_type")
        if kind == MSG_DOCK_MSG_ACK:
            self._pending_uploads.pop(raw.get("id"), None)
        elif kind == MSG_DOCK_DELIVER:
            self._deliver({"message_id": raw["id"], "name": (raw.get("payload") or {}).get("name", raw["id"]),
                           "created_at": raw["created_at"], "hops": raw["hops"]})
