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
from src.scenario import ALL_NODES, DOCK_RADIUS, SENSORS, initial_position, role
from src.sensor import make_sensor


def run(protocol: str, viz: bool) -> Dict[str, float]:
    """Roda um cenário e grava o log de eventos em logs/<protocolo>.log."""
    METRICS.reset()
    PS_METRICS.reset()
    duration = VIZ_DURATION if viz else SIMULATION_DURATION
    config.T2_SCENARIO = protocol == "pubsub"  # satélites afastados no início + sensores
    # Últimas voltas só entregam: 1 no T1; 2 no T2, porque a publicação de um satélite espera
    # nele até o acoplamento (até ~36 s) e os outros satélites ainda precisam acoplar para pedi-la
    drain_turns = 2 if config.T2_SCENARIO else 1
    if duration <= drain_turns * ROTATION_PERIOD:
        print(f"\n[AVISO] {duration / ROTATION_PERIOD:.0f} volta(s): as últimas {drain_turns} só entregam, então "
              f"nenhuma mensagem será criada. Use mais de {drain_turns} (TURNS / VIZ_TURNS em src/config.py).\n")
    config.TRAFFIC_END = duration - drain_turns * ROTATION_PERIOD
    log_path = eventlog.open_log(
        protocol, f"# Protocolo: {protocol} | modo: {'visualizador 3D' if viz else 'headless'}"
                  f" | duração: {duration:.0f}s")
    print(f"\n>>> Log de eventos sendo gravado em: {log_path}\n")
    builder = SimulationBuilder(SimulationConfiguration(
        duration=duration,
        real_time=False,  # o ritmo do modo 3D fica com o PacingHandler (prazos absolutos)
        execution_logging=False,
    ))

    classes = {r: make_node(protocol, viz, r) for r in ("core", "satellite")}
    for node_id in ALL_NODES:  # a ordem de criação define os IDs (0..8 = Core, 9..12 = satélites)
        builder.add_node(classes[role(node_id)], initial_position(node_id))
    if config.T2_SCENARIO:
        sensor_class = make_sensor(viz)
        for sensor in SENSORS:  # 13..24, na sequência
            assert builder.add_node(sensor_class, initial_position(sensor)) == sensor

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
        config.T2_SCENARIO = False
        summary = METRICS.summary()
        summary.update(METRICS.recovery(duration))
        if protocol == "pubsub":
            summary.update(PS_METRICS.summary(duration))
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


# Pub/Sub (uma execução): (métrica, chave no resumo, formato, descrição) — tabela vertical.
# As 4 métricas do enunciado vêm primeiro; definições em `pubsub.py` (Métricas de pub/sub).
PS_ROWS = [
    ("MDR (%)", "ps_mdr", "{:.2f}", "Publicações que chegaram a TODOS os assinantes elegíveis / publicações com ao menos um elegível × 100."),
    ("Fora de ordem (%)", "ps_out_of_order_pct", "{:.2f}", "Entregas que chegaram depois de uma publicação mais nova do mesmo autor, no mesmo tópico, para o mesmo assinante / entregues × 100."),
    ("Latência média (s)", "ps_lat_mean", "{:.2f}", "Da publicação à entrega, só publicações posteriores à assinatura (ao vivo). Inclui o tempo que a publicação de um satélite espera nele até acoplar e o que a entrega a um satélite espera até ele acoplar."),
    ("Latência p95 (s)", "ps_lat_p95", "{:.2f}", "Percentil 95 da latência ao vivo."),
    ("Latência p99 (s)", "ps_lat_p99", "{:.2f}", "Percentil 99 da latência ao vivo."),
    ("Recuperação após falha, média (s)", "ps_rec_mean", "{:.2f}", "Entre as falhas recuperadas: do fim da falha até todo o Core ter de novo rota aos outros 8 nós, o PSPeer mais próximo de antes e as linhas de satélite iguais ao estado real (amostras a cada 0,1 s)."),
    ("Recuperação após falha, máx. (s)", "ps_rec_max", "{:.2f}", "Pior caso da linha anterior."),
    ("Falhas recuperadas", "ps_recovered", "{}", "Falhas recuperadas em até 10 s (de `Falhas de core`)."),
    ("Falhas de core", "ps_failures", "{}", "Janelas em que um nó do Core ficou incomunicável (1 s a cada 30 s) e cuja medição coube na simulação (terminou até 10 s antes do fim ou recuperou antes)."),
    ("Publicações", "ps_pubs", "{}", "Publicações criadas: Core (sorteio a cada PS_INTERVAL s) e satélites (uma por sensor encontrado em cada viagem)."),
    ("Publicações de satélites", "ps_pubs_sat", "{}", "Das publicações, as de satélites (sensor par → T2, ímpar → T1)."),
    ("Publicações com assinante elegível", "ps_pubs_with_subs", "{}", "Base do MDR: publicações com ao menos um assinante cujo filtro contém a região delas."),
    ("Assinaturas", "ps_subs", "{}", "Assinaturas criadas (cada nó assina cada tópico no máximo uma vez)."),
    ("Entregas esperadas", "ps_expected", "{}", "Pares (assinante, publicação): o assinante assina o tópico com filtro que contém a região da publicação (inclusive a fila anterior à assinatura); nunca ao próprio autor."),
    ("Entregues", "ps_delivered", "{}", "Entregas esperadas que chegaram."),
    ("Taxa por par (%)", "ps_pair_rate", "{:.2f}", "Entregues / esperadas × 100."),
    ("Falsos positivos", "ps_false_pos", "{}", "Entregas que a regra não exigia (filtro ou tópico errado)."),
    ("Duplicadas", "ps_duplicates", "{}", "Cópias extras da mesma publicação no mesmo assinante (descartadas por ele)."),
    ("Entregas ao vivo", "ps_live", "{}", "Entregas de publicações posteriores à assinatura (base da latência)."),
    ("Entregas da fila antiga", "ps_backlog", "{}", "Entregas de publicações anteriores à assinatura."),
    ("Latência da fila antiga (s)", "ps_backlog_lat_mean", "{:.2f}", "Da assinatura à entrega, para a fila antiga (média)."),
    ("Saltos médios", "ps_hops_mean", "{:.2f}", "Transmissões de rádio do autor ao PSPeer, entre PSPeers (sync) e do PSPeer ao assinante."),
    ("Convergência de assinatura (s)", "ps_sub_conv_mean", "{:.3f}", "Da criação da assinatura até os 3 PSPeers a conhecerem (média). Inclui o tempo até o satélite acoplar."),
    ("Assinaturas não sincronizadas", "ps_sub_unsynced", "{}", "Assinaturas que algum PSPeer nunca conheceu (sync perdido numa falha; sem retransmissão)."),
    ("Vazão (entregas/min)", "ps_throughput", "{:.1f}", "Entregues por minuto simulado."),
    ("Tx dados", "data_tx", "{}", "Pacotes de dados: pedidos ao PSPeer, entregas aos assinantes e dados do SwCore até os satélites."),
    ("Tx controle", "control_tx", "{}", "Pacotes de controle: atualizações e pedidos da RT de satélites do SwCore, confirmações de upload e syncs entre PSPeers. Beacons de enlace (inclusive os que levam a RT do Core) ficam de fora, como no T1."),
]


def _ps_table(summary: Dict[str, float]) -> str:
    lines = ["| Métrica | Valor | Descrição |", "| :--- | :---: | :--- |"]
    lines += [f"| {title} | {_cell(summary[key], fmt)} | {text} |" for title, key, fmt, text in PS_ROWS]
    return "\n".join(lines)


def print_pubsub(summary: Dict[str, float]) -> None:
    print(_ps_table(summary))


def write_pubsub_to_file(summary: Dict[str, float], filename) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Resultados do Pub/Sub sobre o SwCore do professor\n\n" + _ps_table(summary) + "\n")
