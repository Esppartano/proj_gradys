"""
Motor: monta e roda a simulação de um único cenário (Swarm Core em V);
só o protocolo muda. O ponto de entrada é o menu em `main.py`, na raiz.
"""
from typing import Dict, List

from gradysim.simulator.handler.communication import CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityConfiguration, MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src.config import COMM_DELAY, COMM_RANGE, MOBILITY_UPDATE, SIMULATION_DURATION
from src import eventlog
from src.metrics import METRICS
from src.nodes import make_node
from src.radio import SwarmCommunicationHandler
from src.scenario import ALL_NODES, initial_position


def run(protocol: str, viz: bool) -> Dict[str, float]:
    """Roda um cenário e grava o log de eventos em logs/<protocolo>.log."""
    METRICS.reset()
    log_path = eventlog.open_log(
        protocol, f"# Protocolo: {protocol} | modo: {'visualizador 3D' if viz else 'headless'}"
                  f" | duração: {SIMULATION_DURATION:.0f}s")
    print(f"\n>>> Log de eventos sendo gravado em: {log_path}\n")
    builder = SimulationBuilder(SimulationConfiguration(
        duration=SIMULATION_DURATION,
        real_time=viz,
        execution_logging=False,
    ))

    Node = make_node(protocol, viz)
    for node_id in ALL_NODES:  # a ordem de criação define os IDs (0 = BS)
        builder.add_node(Node, initial_position(node_id))

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler(MobilityConfiguration(update_rate=MOBILITY_UPDATE)))
    builder.add_handler(SwarmCommunicationHandler(CommunicationMedium(transmission_range=COMM_RANGE, delay=COMM_DELAY)))
    if viz:
        builder.add_handler(VisualizationHandler(VisualizationConfiguration(
            x_range=(-50.0, 50.0),
            y_range=(-50.0, 50.0),
            z_range=(0.0, 20.0),
            information_collection_interval=0.1,
            update_rate=0.1,
            open_browser=True,
        )))

    try:
        builder.build().start_simulation()
    finally:
        summary = METRICS.summary()
        eventlog.close_log(_table([{"protocol": protocol, **summary}]))
    print(f"\n>>> Log de eventos salvo em: {log_path}\n")
    return summary


# (título, chave em METRICS.summary(), formato, legenda)
COLUMNS = [
    ("Protocolo", "protocol", "{}", "Protocolo de roteamento usado."),
    ("Criadas", "created", "{}", "Mensagens de dados criadas pelos endpoints (satélites e BS); igual em todos."),
    ("Entregues", "delivered", "{}", "Mensagens que chegaram ao destino (só a primeira chegada conta)."),
    ("PDR%", "pdr", "{:.1f}", "Taxa de entrega: entregues / criadas × 100. Mede a eficácia."),
    ("Lat. média(s)", "lat_mean", "{:.2f}", "Tempo médio entre criar e entregar (só das entregues)."),
    ("Lat. mediana(s)", "lat_median", "{:.2f}", "Mediana desse tempo (menos sensível a extremos)."),
    ("Saltos médios", "hops_mean", "{:.2f}", "Transmissões de rádio que a mensagem entregue percorreu, em média."),
    ("Tx dados", "data_tx", "{}", "Pacotes de dados transmitidos (um lote do DTN conta como 1)."),
    ("Msgs dados tx", "data_msgs_tx", "{}", "Mensagens de dados transmitidas, contando cada uma dentro dos lotes do DTN."),
    ("Tx controle", "control_tx", "{}", "Pacotes de controle do protocolo: avisos de alcance (SwCore), vetores-resumo (DTN), ACKs do receptor (Flooding). Beacons de formação ficam de fora."),
    ("Tx / entrega", "tx_per_delivery", "{:.2f}", "(Tx dados + Tx controle) / entregues: custo em transmissões de cada entrega. Mede a eficiência."),
    ("Rx redund.", "redundant_receptions", "{}", "Vezes que um nó recebeu uma mensagem que já tinha visto (desperdício)."),
    ("Entregas dupl.", "duplicate_deliveries", "{}", "Cópias extras da mesma mensagem que chegaram ao destino."),
    ("Desc. TTL", "ttl_drops", "{}", "Mensagens descartadas por esgotar o limite de saltos (Flooding/GeoCast)."),
    ("Podas", "pruned", "{}", "Retransmissões evitadas: self-pruning no Flooding (todos os vizinhos já foram cobertos) ou nó fora da zona-alvo no GeoCast."),
    ("Sem rota", "no_route", "{}", "GeoCast: mensagens descartadas por não haver vizinho mais perto do destino (vazio de cobertura)."),
    ("ACKs origem", "acks_received", "{}", "Flooding: confirmações do receptor que chegaram de volta à origem."),
    ("Expiradas", "expired", "{}", "Mensagens nunca entregues cuja espera venceu: retenção no SwCore ou cópias no DTN."),
    ("Energia", "energy", "{:.0f}", "Energia de rádio: 1 por transmissão + 0,5 por recepção (unidades arbitrárias)."),
]


def _table(results: List[Dict[str, float]]) -> str:
    lines = ["| " + " | ".join(title for title, *_ in COLUMNS) + " |",
             "|" + "|".join(" :---: " for _ in COLUMNS) + "|"]
    for r in results:
        lines.append("| " + " | ".join(fmt.format(r[key]) for _, key, fmt, _ in COLUMNS) + " |")
    return "\n".join(lines)


def print_table(results: List[Dict[str, float]]):
    """Imprime os resultados como tabela Markdown (pronta para o relatório)."""
    print(_table(results))


def _legend() -> str:
    lines = ["## Legenda", ""]
    lines += [f"- **{title}**: {legend}" for title, _, _, legend in COLUMNS]
    return "\n".join(lines)


def write_table_to_file(results: List[Dict[str, float]], filename):
    """Grava a tabela de resultados seguida da legenda das colunas."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Resultados\n\n" + _table(results) + "\n\n" + _legend() + "\n")
