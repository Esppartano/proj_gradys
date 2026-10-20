"""
Flooding com supressão de duplicatas, TTL, self-pruning e ACK do receptor.

Segue o slide: repassar a "alguns ou todos" os vizinhos, com TTL definido pelo
tamanho e densidade da rede; o receptor confirma o recebimento.

- Supressão de duplicatas: cada nó retransmite cada mensagem no máximo uma vez.
- TTL (FLOOD_TTL = diâmetro da rede): decrementado a cada salto; em 0, descarta.
- Self-pruning (Lim & Kim, 2001): quem transmite anexa a sua lista de vizinhos
  (`covered`, da camada de enlace: informação local de 1 salto). O receptor só
  retransmite se tiver algum vizinho que não esteja nessa lista nem seja o
  próprio remetente; senão, a retransmissão seria inútil. Quem acabou de me
  enviar um pacote também conta como vizinho: um satélite pode transmitir
  antes de o seu primeiro beacon chegar (beacon de 0,5 s contra 0,2 s do Core),
  e sem isso ele ficaria de fora da lista e a poda seria indevida (achado do agy).
- ACK: ao entregar pela primeira vez, o destino inunda um ACK (controle) de
  volta à origem, com as mesmas regras. O ACK só confirma a entrega; não há
  retransmissão (a topologia pode mudar no meio, como alerta o slide).

Armazenamento: só na origem (regra comum a todos os protocolos, em
`RoutingMixin._can_originate`): o satélite acumula o que cria enquanto está
isolado e inunda ao ganhar o primeiro vizinho. Nos intermediários não há
armazenamento: se não existir caminho até o destino no instante da inundação,
a mensagem se perde (não atravessa partições).
"""
from src.config import FLOOD_TTL, LINK_TIMEOUT
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import label


class FloodingMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self._seen_acks: set = set()
        self._heard_from: dict = {}  # remetente → último instante em que me enviou um pacote

    def _heard(self) -> set:
        """Vizinhos pela camada de enlace + remetentes ouvidos há pouco."""
        now = self.provider.current_time()
        recent = {p for p, t in self._heard_from.items() if now - t <= LINK_TIMEOUT}
        return set(self.neighbors()) | recent

    # ── Inundação com self-pruning ────────────────────────────────────────

    def _flood(self, packet: dict, control: bool = False) -> None:
        """Difunde anexando os vizinhos que esta transmissão cobre."""
        self._broadcast({**packet, "covered": sorted(self._heard())}, control=control)

    def _prunes(self, raw: dict) -> bool:
        """Self-pruning: todos os meus vizinhos já ouviram o remetente?"""
        uncovered = self._heard() - set(raw.get("covered", ())) - {raw["sender_id"]}
        return not uncovered

    def _relay(self, raw: dict, control: bool) -> bool:
        """Regras comuns a dados e ACKs: TTL e self-pruning. True se retransmitiu."""
        ttl = raw["ttl"] - 1
        if ttl <= 0:
            METRICS.ttl_drops += 1
            self._note("ttl_drop", f"Descartou {raw.get('name', 'ACK')} (TTL esgotado)", "ttl_drops")
            return False
        if self._prunes(raw):
            METRICS.pruned += 1
            self.stats["pruned"] += 1
            return False
        self._flood({**raw, "ttl": ttl, "hops": raw.get("hops", 0) + 1, "sender_id": self.node_id},
                    control=control)
        return True

    # ── Dados ─────────────────────────────────────────────────────────────

    def _originate(self, message: m.DataMessage) -> None:
        self._seen.add(message["message_id"])
        self._flood(self._forward_copy(message, ttl=FLOOD_TTL))

    def _on_routing(self, raw: dict) -> None:
        self._heard_from[raw["sender_id"]] = self.provider.current_time()
        if raw["msg_type"] == m.FLOOD_ACK:
            self._on_ack(raw)
            return
        if raw["msg_type"] != m.DATA:
            return
        if raw["destination"] == self.node_id:
            if raw["message_id"] not in self._seen:  # primeira chegada: confirma
                self._seen.add(raw["message_id"])
                self._send_ack(raw)
            self._deliver(raw)
            return
        if raw["message_id"] in self._seen:
            self._redundant()
            return
        self._seen.add(raw["message_id"])
        if self._relay(raw, control=False):
            self._note("forwarded", f"Retransmitiu {raw['name']} (TTL={raw['ttl'] - 1})", "forwarded")

    # ── ACK do receptor ───────────────────────────────────────────────────

    def _send_ack(self, message: m.DataMessage) -> None:
        self._seen_acks.add(message["message_id"])
        self._flood({"msg_type": m.FLOOD_ACK, "sender_id": self.node_id, "ack_id": message["message_id"],
                     "origin_id": message["origin_id"], "ttl": FLOOD_TTL}, control=True)
        self._note("acked", f"Confirmou {message['name']} para {label(message['origin_id'])}")

    def _on_ack(self, raw: dict) -> None:
        if raw["ack_id"] in self._seen_acks:
            return
        self._seen_acks.add(raw["ack_id"])
        if raw["origin_id"] == self.node_id:
            METRICS.acks_received += 1
            self._note("acked", f"Recebeu ACK da mensagem {raw['ack_id']}")
            return
        self._relay(raw, control=True)
