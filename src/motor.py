"""
Motor: monta e roda a simulação de um único cenário (Swarm Core em V);
só o protocolo muda. O ponto de entrada é o menu em `main.py`, na raiz.
"""
from math import isnan
from typing import Dict, List

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility import MobilityConfiguration, MobilityHandler
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationConfiguration, VisualizationHandler
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from src import config
from src.config import (
    AWAY_DISTANCE, COMM_DELAY, COMM_RANGE, MOBILITY_UPDATE, ROTATION_PERIOD, SIMULATION_DURATION,
    VIZ_DURATION, VIZ_SPEEDUP,
)
from src import eventlog
from src.metrics import METRICS
from src.pubsub import PS_METRICS
from src.nodes import make_node
from src.pacing import PacingHandler
from src.scenario import ALL_NODES, DOCK_RADIUS, initial_position


def run(protocol: str, viz: bool) -> Dict[str, float]:
    """Roda um cenário e grava o log de eventos em logs/<protocolo>.log."""
    METRICS.reset()
    PS_METRICS.reset()
    duration = VIZ_DURATION if viz else SIMULATION_DURATION
    if duration < 2 * ROTATION_PERIOD:
        print(f"\n[AVISO] {duration / ROTATION_PERIOD:.0f} volta(s): a última volta só entrega, então "
              "nenhuma mensagem será criada. Use pelo menos 2 (TURNS / VIZ_TURNS em src/config.py).\n")
    config.TRAFFIC_END = duration - ROTATION_PERIOD  # última volta: só entrega
    log_path = eventlog.open_log(
        protocol, f"# Protocolo: {protocol} | modo: {'visualizador 3D' if viz else 'headless'}"
                  f" | duração: {duration:.0f}s")
    print(f"\n>>> Log de eventos sendo gravado em: {log_path}\n")
    builder = SimulationBuilder(SimulationConfiguration(
        duration=duration,
        real_time=False,  # o ritmo do modo 3D fica com o PacingHandler (prazos absolutos)
        execution_logging=False,
    ))

    Node = make_node(protocol, viz)
    for node_id in ALL_NODES:  # a ordem de criação define os IDs (0..8 = Core, 9..12 = satélites)
        builder.add_node(Node, initial_position(node_id))

    builder.add_handler(TimerHandler())
    builder.add_handler(MobilityHandler(MobilityConfiguration(update_rate=MOBILITY_UPDATE)))
    builder.add_handler(CommunicationHandler(CommunicationMedium(transmission_range=COMM_RANGE, delay=COMM_DELAY)))
    if viz:
        builder.add_handler(PacingHandler(VIZ_SPEEDUP))
        extent = DOCK_RADIUS + AWAY_DISTANCE + 10.0
        builder.add_handler(VisualizationHandler(VisualizationConfiguration(
            x_range=(-extent, extent),
            y_range=(-extent, extent),
            z_range=(0.0, 30.0),
            # ≈ 10 quadros por segundo na tela, mas nunca mais que 0,5 s simulados (< acoplamento de 2 s)
            information_collection_interval=min(0.1 * VIZ_SPEEDUP, 0.5),
            update_rate=0.1,
            open_browser=True,
        )))

    try:
        builder.build().start_simulation()
    finally:
        summary = METRICS.summary()
        summary.update(METRICS.recovery(duration))
        if protocol == "pubsub":
            summary.update(PS_METRICS.summary(duration))
            delivered = summary["ps_delivered"]
            summary["ps_energy_per_delivery"] = summary["energy"] / delivered if delivered else float("nan")
        eventlog.close_log(_ps_table(summary) if protocol == "pubsub"
                          else _table([{"protocol": protocol, **summary}]))
    print(f"\n>>> Log de eventos salvo em: {log_path}\n")
    return summary


# (título, chave em METRICS.summary(), formato, legenda)
COLUMNS = [
    ("Protocolo", "protocol", "{}", "Protocolo de roteamento usado."),
    ("Criadas", "created", "{}", "Mensagens criadas pelos satélites (uma por acoplamento, para o satélite do eixo oposto); igual em todos."),
    ("Entregues", "delivered", "{}", "Mensagens que chegaram ao destino (só a primeira chegada conta)."),
    ("PDR%", "pdr", "{:.1f}", "Taxa de entrega: entregues / criadas × 100. Mede a eficácia."),
    ("Lat. média(s)", "lat_mean", "{:.2f}", "Tempo médio entre criar e entregar (só das entregues)."),
    ("Lat. mediana(s)", "lat_median", "{:.2f}", "Mediana desse tempo (menos sensível a extremos)."),
    ("Lat. máx.(s)", "lat_max", "{:.2f}", "Maior tempo entre criar e entregar."),
    ("Saltos médios", "hops_mean", "{:.2f}", "Transmissões de rádio que a mensagem entregue percorreu, em média."),
    ("Tx dados", "data_tx", "{}", "Pacotes de dados transmitidos (um lote do DTN conta como 1)."),
    ("Msgs dados tx", "data_msgs_tx", "{}", "Mensagens de dados transmitidas, contando cada uma dentro dos lotes do DTN."),
    ("Tx controle", "control_tx", "{}", "Pacotes de controle do protocolo: avisos de alcance (SwCore), vetores-resumo (DTN), ACKs do receptor (Flooding), buscas e respostas de rota (GeoCast). Beacons de formação ficam de fora."),
    ("Tx / entrega", "tx_per_delivery", "{:.2f}", "(Tx dados + Tx controle) / entregues: custo em transmissões de cada entrega. Mede a eficiência."),
    ("Rx redund.", "redundant_receptions", "{}", "Vezes que um nó recebeu uma mensagem que já tinha visto (desperdício)."),
    ("Entregas dupl.", "duplicate_deliveries", "{}", "Cópias extras da mesma mensagem que chegaram ao destino."),
    ("Desc. TTL", "ttl_drops", "{}", "Mensagens descartadas por esgotar o limite de saltos (Flooding/GeoCast)."),
    ("Podas", "pruned", "{}", "Retransmissões evitadas: self-pruning no Flooding (todos os vizinhos já foram cobertos) ou nó fora da zona-alvo no GeoCast."),
    ("Contornos", "bypasses", "{}", "GeoCast: vazios de cobertura contornados pela busca de rota (Choi et al.)."),
    ("Sem rota", "no_route", "{}", "GeoCast: mensagens descartadas num vazio de cobertura que a busca de rota não conseguiu contornar."),
    ("ACKs origem", "acks_received", "{}", "Flooding: confirmações do receptor que chegaram de volta à origem."),
    ("Retx salto", "hop_retx", "{}", "SwCore: retransmissões de um dado por falta de confirmação (HOP_ACK) do próximo salto, ex.: vizinho em falha."),
    ("Energia", "energy", "{:.0f}", "Energia de rádio: 1 por transmissão + 0,5 por recepção (unidades arbitrárias)."),
]


def _cell(value, fmt: str) -> str:
    """Formata a célula; métricas sem amostra (ex.: latência sem entregas) viram n/d."""
    if isinstance(value, float) and isnan(value):
        return "n/d"
    return fmt.format(value)


def _table(results: List[Dict[str, float]]) -> str:
    lines = ["| " + " | ".join(title for title, *_ in COLUMNS) + " |",
             "|" + "|".join(" :---: " for _ in COLUMNS) + "|"]
    for r in results:
        lines.append("| " + " | ".join(_cell(r[key], fmt) for _, key, fmt, _ in COLUMNS) + " |")
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


# Pub/Sub (uma execução): (métrica, chave no resumo, formato, descrição) — tabela vertical
PS_ROWS = [
    ("Publicações", "ps_pubs", "{}", "Publicações criadas (Core: sorteio a cada PS_INTERVAL s; satélites: uma por acoplamento)."),
    ("Assinaturas", "ps_subs", "{}", "Assinaturas criadas; uma nova do mesmo tópico substitui o filtro anterior do nó."),
    ("Entregas esperadas", "ps_expected", "{}", "Pares (assinante, publicação) que a regra de entrega exige: filtro vigente na criação da publicação contém a região dela; nunca ao próprio autor."),
    ("Entregues", "ps_delivered", "{}", "Entregas esperadas que chegaram ao assinante."),
    ("MDR (%)", "ps_mdr", "{:.1f}", "Taxa de entrega: entregues / esperadas × 100."),
    ("Falsos positivos", "ps_false_pos", "{}", "Entregas que a regra não exigia (o PSPeer ainda não conhecia o filtro novo do assinante)."),
    ("Falsos negativos", "ps_false_neg", "{}", "Entregas esperadas que não chegaram até o fim da simulação."),
    ("Duplicadas", "ps_duplicates", "{}", "Cópias extras da mesma publicação no mesmo assinante."),
    ("Fora de ordem", "ps_out_of_order", "{}", "Entregas que chegaram depois de uma publicação mais nova do mesmo autor, para o mesmo assinante."),
    ("Fora de ordem (%)", "ps_out_of_order_pct", "{:.2f}", "Fora de ordem / entregas esperadas × 100 (sem falsos positivos)."),
    ("Latência média (s)", "ps_lat_mean", "{:.2f}", "Da criação da publicação à entrega (só entregas esperadas)."),
    ("Latência p95 (s)", "ps_lat_p95", "{:.2f}", "Percentil 95 da latência."),
    ("Latência p99 (s)", "ps_lat_p99", "{:.2f}", "Percentil 99 da latência."),
    ("Saltos médios", "ps_hops_mean", "{:.2f}", "Transmissões de rádio do autor ao PSPeer e do PSPeer ao assinante."),
    ("Convergência de assinatura (s)", "ps_sub_conv_mean", "{:.3f}", "Da criação da assinatura até todos os PSPeers a conhecerem (média)."),
    ("Vazão (entregas/min)", "ps_throughput", "{:.1f}", "Entregas esperadas por minuto simulado."),
    ("Falhas de core", "failures", "{}", "Janelas em que um nó do Core ficou incomunicável (1 s a cada 30 s)."),
    ("Recuperação do roteamento (s)", "rec_routing_mean", "{:.3f}", "Do fim da falha até o core e todos os vizinhos da árvore trocarem SYNC (média)."),
    ("Recuperação do roteamento, máx. (s)", "rec_routing_max", "{:.3f}", "Pior caso da linha anterior."),
    ("Recuperação dos dados (s)", "rec_data_mean", "{:.3f}", "Do fim da falha até o 1º dado confirmado (HOP_ACK) enviado pelo core ou a ele (média; depende do tráfego)."),
    ("Recuperação dos dados, máx. (s)", "rec_data_max", "{:.3f}", "Pior caso da linha anterior."),
    ("Retransmissões por salto", "hop_retx", "{}", "Dados reenviados por falta de HOP_ACK (ex.: próximo salto em falha)."),
    ("Tx dados", "data_tx", "{}", "Pacotes de dados transmitidos (pedidos, syncs e notificações)."),
    ("Tx controle", "control_tx", "{}", "Pacotes de controle: REACH/UNREACH, SYNC e HOP_ACK."),
    ("Energia", "energy", "{:.0f}", "1 por transmissão + 0,5 por recepção (unidades arbitrárias)."),
    ("Energia por entrega", "ps_energy_per_delivery", "{:.2f}", "Energia / entregas esperadas."),
]


def _ps_table(summary: Dict[str, float]) -> str:
    lines = ["| Métrica | Valor | Descrição |", "| :--- | :---: | :--- |"]
    lines += [f"| {title} | {_cell(summary[key], fmt)} | {text} |" for title, key, fmt, text in PS_ROWS]
    return "\n".join(lines)


def print_pubsub(summary: Dict[str, float]) -> None:
    print(_ps_table(summary))


def write_pubsub_to_file(summary: Dict[str, float], filename) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Resultados do Pub/Sub sobre SwCore\n\n" + _ps_table(summary) + "\n")
