"""
DTN Store-Carry-Forward com troca completa no encontro (slide da disciplina).

Segue o slide: entrega eventual pelos nós em movimento; no encontro, os nós
trocam TODAS as mensagens que o outro ainda não tem ("swap all messages").

- Store: cada nó guarda cópias no buffer (limite DTN_BUFFER_SIZE; cada cópia
  expira DTN_MSG_TTL s após a criação da mensagem).
- Vetor-resumo (SUMMARY, controle): ids que tenho no buffer + ids que sei que
  já foram entregues ("aviso de entrega"). É enviado:
    * em unicast, ao ganhar um vizinho novo (encontro);
    * em broadcast, quando o buffer ganha mensagens novas. Isso é necessário
      porque os nós do Core estão sempre em contato e nunca geram "encontro
      novo" entre si (achado da revisão do agy).
- Troca em 2 passos: quem recebe o SUMMARY de A envia a A, num lote (BUNDLE),
  as mensagens que A não tem; se A tem mensagens que ele não tem, responde com
  o próprio SUMMARY, para A fazer o mesmo.
- Aviso de entrega: o destino registra a entrega; os ids entregues viajam nos SUMMARY e
  quem os recebe apaga as cópias. Nenhum nó conhece posições ou estado global.
"""
from collections import OrderedDict
from typing import Dict, Set

from src.config import DTN_BUFFER_SIZE, DTN_MSG_TTL
from src.metrics import METRICS
from src.routing import messages as m
from src.routing.base import RoutingMixin
from src.scenario import label


class DTNMixin(RoutingMixin):

    def initialize(self) -> None:
        super().initialize()
        self._buffer: "OrderedDict[str, m.DataMessage]" = OrderedDict()
        self._delivered: Set[str] = set()                 # avisos de entrega: ids já entregues ao destino
        self._peer_has: Dict[int, Set[str]] = {}          # vizinho → ids que sei que ele tem

    def _can_originate(self) -> bool:
        return True  # a própria mensagem já fica no buffer até haver contato

    # ── Buffer ────────────────────────────────────────────────────────────

    def _purge(self) -> None:
        """Descarta cópias vencidas ou de mensagens já entregues."""
        now = self.provider.current_time()
        for msg_id, msg in list(self._buffer.items()):
            if msg_id in self._delivered:
                del self._buffer[msg_id]
            elif now > msg["created_at"] + DTN_MSG_TTL:
                del self._buffer[msg_id]
                METRICS.record_expired(msg_id)
                self.stats["expired"] += 1

    def _store(self, message: m.DataMessage) -> None:
        if len(self._buffer) >= DTN_BUFFER_SIZE:
            self._buffer.popitem(last=False)
            METRICS.buffer_drops += 1
        self._buffer[message["message_id"]] = message

    def _originate(self, message: m.DataMessage) -> None:
        self._store(message)
        self._announce()

    # ── Troca completa no encontro ────────────────────────────────────────

    def _summary(self) -> dict:
        self._purge()
        return {"msg_type": m.SUMMARY, "sender_id": self.node_id,
                "ids": list(self._buffer), "delivered": sorted(self._delivered)}

    def _announce(self) -> None:
        """Buffer ganhou mensagens novas: avisa os vizinhos atuais."""
        if self.neighbors():
            self._broadcast(self._summary(), control=True)

    def _send_missing(self, peer: int) -> None:
        """Envia ao vizinho, num lote, as mensagens que ele ainda não tem."""
        known = self._peer_has.setdefault(peer, set())
        batch = [msg for msg_id, msg in self._buffer.items() if msg_id not in known]
        if not batch:
            return
        known.update(msg["message_id"] for msg in batch)
        self._note("handoff", f"Enviou {len(batch)} msg(s) a {label(peer)}", "handed_off", len(batch))
        self._unicast({
            "msg_type": m.BUNDLE,
            "sender_id": self.node_id,
            "messages": [self._forward_copy(msg) for msg in batch],
        }, peer, payload=len(batch))

    # ── Eventos ───────────────────────────────────────────────────────────

    def _on_contact(self, peer: int) -> None:
        super()._on_contact(peer)
        self._unicast(self._summary(), peer, control=True)

    def _on_routing(self, raw: dict) -> None:
        kind, peer = raw["msg_type"], raw["sender_id"]
        if kind == m.SUMMARY:
            self._delivered.update(raw["delivered"])
            self._purge()
            # Acumula (não sobrescreve): um lote meu ainda em voo já está contado
            self._peer_has.setdefault(peer, set()).update(raw["ids"], raw["delivered"])
            self._send_missing(peer)
            lacking = set(raw["ids"]) - set(self._buffer) - self._delivered  # ele tem o que eu não tenho
            stale = set(raw["ids"]) & self._delivered                       # ele guarda o que já foi entregue
            if lacking or stale:
                self._unicast(self._summary(), peer, control=True)
        elif kind == m.BUNDLE:
            known = self._peer_has.setdefault(peer, set())
            new = 0  # mensagens guardadas ou entregas novas: há o que anunciar
            for msg in raw["messages"]:
                known.add(msg["message_id"])
                if msg["destination"] == self.node_id:
                    if msg["message_id"] not in self._delivered:
                        new += 1  # o aviso de entrega precisa sair
                    self._deliver(msg)
                    self._delivered.add(msg["message_id"])
                elif msg["message_id"] in self._buffer or msg["message_id"] in self._delivered:
                    self._redundant()
                else:
                    self._store(msg)
                    self.stats["custody"] += 1
                    new += 1
            if new:
                self._announce()

    def finish(self) -> None:
        self._purge()
        super().finish()
