"""
Testes funcionais do Pub/Sub sobre o SwCore do professor (enunciado do T2, TF01–TF06).

Cada teste roda uma simulação curta (cenário do T2, sem falha de core) com as
assinaturas e publicações aleatórias desligadas e um roteiro fixo: quem assina
(tópico e filtro), quem publica e quando. Os satélites continuam publicando o que
coletam dos sensores; os filtros dos roteiros evitam ou usam isso de propósito.

Rodar (na raiz do repositório):  python -m unittest tests.test_pubsub -v

IDs: C1..C9 = 0..8 (Core); S1 = 9 (leste, E), S2 = 10 (norte, N), S3 = 11 (oeste, W),
S4 = 12 (sul, S). Com o satélite começando afastado, os 1ºs acoplamentos são
S4 ≈ 11 s, S2 ≈ 17 s, S1 ≈ 26 s e S3 ≈ 32 s; depois, um a cada ≈ 30 s.
"""
import contextlib
import io
import logging
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

from src import config, eventlog, pubsub
import src.motor as motor
from src.pubsub import PS_METRICS, PubSubClient, PubSubCore

C2, C3, C5, C6, C7, C8, C9 = 1, 2, 4, 5, 6, 7, 8
S1, S2, S3 = 9, 10, 11
DURATION = 150.0

# Roteiro: nó → [(instante, ação, argumentos)]; ação "sub" (tópico, filtro), "pub" (tópico)
# ou "probe" (registra se o satélite está acoplado naquele instante)
SCRIPT: Dict[int, List[Tuple[float, str, tuple]]] = {}
CREATED: Dict[Tuple[int, float], dict] = {}           # (nó, instante) → assinatura/publicação criada
DOCKED: Dict[Tuple[int, float], bool] = {}            # (satélite, instante) → acoplado? (ação "probe")
REPLIES: List[Tuple[int, List[str]]] = []             # respostas do PSPeer a satélites: (satélite, ids)

_orig_init = PubSubClient.initialize
_orig_timer = PubSubClient.handle_timer
_orig_to_sat = PubSubCore._ps_to_satellite


def _init(self) -> None:
    _orig_init(self)
    for i, (at, _, _) in enumerate(SCRIPT.get(self.node_id, [])):
        self.provider.schedule_timer(f"tf_{i}", at)


def _timer(self, timer: str) -> None:
    if not timer.startswith("tf_"):
        return _orig_timer(self, timer)
    at, action, args = SCRIPT[self.node_id][int(timer[3:])]
    if action == "sub":
        CREATED[(self.node_id, at)] = self._subscribe(args[0], list(args[1]))
    elif action == "pub":
        CREATED[(self.node_id, at)] = self._publish(args[0])
    elif action == "probe":
        DOCKED[(self.node_id, at)] = self._docked()
    else:
        raise ValueError(f"ação desconhecida no roteiro: {action}")


def _to_sat(self, sat: int, pubs: List[dict]) -> None:
    REPLIES.append((sat, [p["id"] for p in pubs]))
    _orig_to_sat(self, sat, pubs)


def run(script: Dict[int, List[Tuple[float, str, tuple]]]) -> None:
    SCRIPT.clear()
    SCRIPT.update(script)
    CREATED.clear()
    DOCKED.clear()
    REPLIES.clear()
    with contextlib.redirect_stdout(io.StringIO()):  # avisos do motor ("log sendo gravado em ...")
        motor.run("pubsub", viz=False)


def received(node: int) -> set:
    return {pid for subscriber, pid in PS_METRICS.deliveries if subscriber == node}


SAVED = {}


def setUpModule() -> None:
    SAVED.update(failure=config.CORE_FAILURE, duration=config.SIMULATION_DURATION,
                 traffic_end=config.TRAFFIC_END, sub=pubsub.PS_SUBSCRIBE_PROB, pub=pubsub.PS_PUBLISH_PROB,
                 log_dir=eventlog.LOG_DIR, logging=logging.root.manager.disable)
    SAVED["tmp"] = tempfile.TemporaryDirectory()
    eventlog.LOG_DIR = Path(SAVED["tmp"].name)  # não sobrescreve logs/pubsub.log das execuções reais
    logging.disable(logging.INFO)  # o GrADySim registra início/fim de cada simulação
    config.CORE_FAILURE = False
    config.SIMULATION_DURATION = motor.SIMULATION_DURATION = DURATION
    pubsub.PS_SUBSCRIBE_PROB = pubsub.PS_PUBLISH_PROB = 0.0  # só o roteiro assina e o Core só publica nele
    PubSubClient.initialize = _init
    PubSubClient.handle_timer = _timer
    PubSubCore._ps_to_satellite = _to_sat


def tearDownModule() -> None:
    logging.disable(SAVED["logging"])
    eventlog.LOG_DIR = SAVED["log_dir"]
    SAVED["tmp"].cleanup()
    config.CORE_FAILURE = SAVED["failure"]
    config.SIMULATION_DURATION = motor.SIMULATION_DURATION = SAVED["duration"]
    config.TRAFFIC_END = SAVED["traffic_end"]
    pubsub.PS_SUBSCRIBE_PROB, pubsub.PS_PUBLISH_PROB = SAVED["sub"], SAVED["pub"]
    PubSubClient.initialize = _orig_init
    PubSubClient.handle_timer = _orig_timer
    PubSubCore._ps_to_satellite = _orig_to_sat


class FunctionalTests(unittest.TestCase):

    def assertNoWrongDelivery(self) -> None:
        """Nenhum assinante recebeu algo que a regra não exige, nem em dobro."""
        self.assertEqual(set(PS_METRICS.deliveries) - PS_METRICS.expected(), set())
        self.assertEqual(PS_METRICS.duplicates, 0)

    def test_tf01_one_eligible_subscriber(self):
        """TF01: publicação com um assinante elegível → mensagem entregue."""
        run({C3: [(1.0, "sub", ("T1", ["C"]))], C7: [(10.0, "pub", ("T1",))]})
        pub = CREATED[(C7, 10.0)]
        self.assertIn(pub["id"], received(C3))
        self.assertNoWrongDelivery()

    def test_tf02_many_eligible_subscribers(self):
        """TF02: publicação com múltiplos assinantes elegíveis (Core e satélite) → entrega a todos."""
        run({C3: [(1.0, "sub", ("T2", ["C"]))], C9: [(1.0, "sub", ("T2", ["C", "N"]))],
             S1: [(1.0, "sub", ("T2", ["C"]))], C5: [(10.0, "pub", ("T2",))]})
        pub = CREATED[(C5, 10.0)]
        for subscriber in (C3, C9, S1):
            self.assertIn(pub["id"], received(subscriber), f"não chegou a {subscriber}")
        self.assertNoWrongDelivery()

    def test_tf03_incompatible_filter(self):
        """TF03: filtro incompatível → mensagem não entregue (e a compatível, sim)."""
        run({C3: [(1.0, "sub", ("T1", ["N", "S"]))], C9: [(1.0, "sub", ("T1", ["C"]))],
             C7: [(10.0, "pub", ("T1",))]})
        pub = CREATED[(C7, 10.0)]
        self.assertNotIn(pub["id"], received(C3))   # filtro {N,S}, publicação da região C
        self.assertIn(pub["id"], received(C9))      # controle: filtro {C}
        self.assertNoWrongDelivery()

    def test_tf04_core_publication(self):
        """TF04: publicação por UAV do Core → entrega aos assinantes elegíveis (Core e satélite)."""
        run({C8: [(1.0, "sub", ("T1", ["C"]))], S2: [(1.0, "sub", ("T1", ["C", "N"]))],
             C2: [(10.0, "pub", ("T1",))]})
        pub = CREATED[(C2, 10.0)]
        self.assertEqual(pub["region"], "C")
        self.assertIn(pub["id"], received(C8))
        self.assertIn(pub["id"], received(S2))
        self.assertNoWrongDelivery()

    def test_tf05_core_subscription(self):
        """TF05: assinatura por UAV do Core → recebimento das publicações, inclusive a fila
        anterior à assinatura (S1, leste, publica em T2 ao encontrar o sensor par X14)."""
        run({C6: [(40.0, "sub", ("T2", ["E"]))]})
        backlog = {p["id"] for p in PS_METRICS.pubs.values()
                   if p["publisher"] == S1 and p["topic"] == "T2" and p["created_at"] < 40.0}
        self.assertTrue(backlog, "S1 deveria ter publicado em T2 (sensor par) antes da assinatura")
        self.assertLessEqual(backlog, received(C6))
        self.assertNoWrongDelivery()

    def test_tf06_returning_subscriber_gets_only_unread(self):
        """TF06: satélite que volta depois de consumir → recebe só as não lidas, guardadas."""
        run({S3: [(1.0, "sub", ("T1", ["C"])), (45.0, "probe", ())],
             C2: [(5.0, "pub", ("T1",)), (45.0, "pub", ("T1",))]})
        first, second = CREATED[(C2, 5.0)]["id"], CREATED[(C2, 45.0)]["id"]
        arrival = PS_METRICS.deliveries
        self.assertLess(arrival[(S3, first)], 45.0)   # consumida no 1º acoplamento
        self.assertFalse(DOCKED[(S3, 45.0)], "S3 deveria estar longe do Core quando a 2ª é publicada")
        # Respostas do PSPeer a cada solicitação (uma por acoplamento): a 1ª só com a 1ª
        # publicação; a do retorno só com a não lida; nos acoplamentos seguintes, nada.
        self.assertEqual([ids for sat, ids in REPLIES if sat == S3], [[first], [second]])
        self.assertEqual({first, second}, received(S3))
        self.assertNoWrongDelivery()


if __name__ == "__main__":
    unittest.main()
