import sys
import time
from typing import Dict, Any, List, Tuple, Optional

from gradysim.simulator.handler.communication import CommunicationHandler, CommunicationMedium
from gradysim.simulator.handler.mobility.massless import MasslessMobilityHandler, MasslessMobilityConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler, VisualizationConfiguration
from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration

from base_protocol import METRICS
from flooding_protocol import FloodingProtocol
from dtn_protocol import DTNProtocol
from dtn_multi_mule_protocol import DTNMultiMuleProtocol
from geocast_protocol import GeoCastProtocol


# -------------------------------------------------------------------
# Configuração do Visualizador 3D Web
# -------------------------------------------------------------------
def create_vis_config(x_max: float = 150.0, y_range=(-50.0, 50.0)) -> VisualizationConfiguration:
    return VisualizationConfiguration(
        information_collection_interval=0.05,
        update_rate=0.05,
        x_range=(-20.0, x_max),
        y_range=y_range,
        z_range=(0.0, 40.0),
        host="localhost",
        port=5678,
        open_browser=True
    )


# -------------------------------------------------------------------
# Cenário 1: DTN Tradicional (1 Mula Móvel - Store-Carry-Forward)
# -------------------------------------------------------------------
def run_dtn_single_mule(real_time: bool = True, enable_vis: bool = True) -> Dict[str, Any]:
    METRICS.reset()
    sim_config = SimulationConfiguration(duration=50.0, real_time=real_time)
    builder = SimulationBuilder(configuration=sim_config)

    medium = CommunicationMedium(transmission_range=35.0, delay=0.01)
    builder.add_handler(CommunicationHandler(communication_medium=medium))
    builder.add_handler(TimerHandler())
    builder.add_handler(MasslessMobilityHandler(MasslessMobilityConfiguration(default_speed=12.0)))

    if enable_vis:
        builder.add_handler(VisualizationHandler(configuration=create_vis_config()))

    builder.add_node(DTNProtocol, (0.0, 0.0, 5.0))     # 0: Estação Base
    builder.add_node(DTNProtocol, (10.0, 0.0, 15.0))   # 1: Drone Mula
    builder.add_node(DTNProtocol, (120.0, 0.0, 15.0))  # 2: Alvo Remoto

    print("\n" + "=" * 65)
    print(" INICIANDO: DTN TRADICIONAL (1 Mula Móvel)")
    print(" Topologia: Base (0) -> Mula (1) -> Alvo (2) -> Mula (1) -> Base (0)")
    if enable_vis:
        print(" • Visualizador 3D: https://project-gradys.github.io/gradys-sim-nextgen-visualization/")
        print(" • Aquecimento inicial: 3.0 segundos para conexão do navegador")
        print(" • Velocidade de voo: 12 m/s | Tempo de permanência no alvo: 2.5s")
    print("=" * 65 + "\n")

    sim = builder.build()
    start_wall = time.time()
    sim.start_simulation()
    elapsed_wall = time.time() - start_wall

    METRICS.print_summary("DTN Tradicional (1 Mula)")
    return {
        "scenario": "DTN (1 Mula)",
        "pdr": (METRICS.data_delivered / METRICS.data_sent * 100) if METRICS.data_sent > 0 else 0,
        "latency": METRICS.delivery_latency,
        "rtt": METRICS.round_trip_time,
        "transmissions": METRICS.total_transmissions,
        "hops": METRICS.hops,
        "success": METRICS.mission_success,
        "wall_time": elapsed_wall
    }


# -------------------------------------------------------------------
# Cenário 2: DTN Multi-Mula (Arsheen et al. - Cadeia de Rendezvous)
# -------------------------------------------------------------------
def run_dtn_multi_mule(real_time: bool = True, enable_vis: bool = True) -> Dict[str, Any]:
    METRICS.reset()
    sim_config = SimulationConfiguration(duration=55.0, real_time=real_time)
    builder = SimulationBuilder(configuration=sim_config)

    medium = CommunicationMedium(transmission_range=25.0, delay=0.01)
    builder.add_handler(CommunicationHandler(communication_medium=medium))
    builder.add_handler(TimerHandler())
    builder.add_handler(MasslessMobilityHandler(MasslessMobilityConfiguration(default_speed=12.0)))

    if enable_vis:
        builder.add_handler(VisualizationHandler(configuration=create_vis_config(x_max=150.0, y_range=(-60.0, 60.0))))

    # Topologia do artigo de Arsheen et al. (2020)
    builder.add_node(DTNMultiMuleProtocol, (0.0, 0.0, 5.0))     # 0: Base P (Fonte)
    builder.add_node(DTNMultiMuleProtocol, (5.0, 0.0, 15.0))    # 1: Mula Q (Base -> Rendezvous)
    builder.add_node(DTNMultiMuleProtocol, (55.0, 0.0, 15.0))   # 2: Mula R (Rendezvous -> Destino)
    builder.add_node(DTNMultiMuleProtocol, (120.0, 0.0, 10.0))  # 3: Destino
    builder.add_node(DTNMultiMuleProtocol, (25.0, 35.0, 10.0))  # 4: Nó S (Norte - Isolado)
    builder.add_node(DTNMultiMuleProtocol, (80.0, -30.0, 10.0)) # 5: Nó T (Sul - Isolado)

    print("\n" + "=" * 65)
    print(" INICIANDO: DTN MULTI-MULA (Arsheen et al. 2020)")
    print(" Topologia: P (0) -> Mula Q (1) -> Rendezvous (R) -> Destino (3)")
    if enable_vis:
        print(" • Visualizador 3D: https://project-gradys.github.io/gradys-sim-nextgen-visualization/")
        print(" • Aquecimento inicial: 3.0 segundos para conexão do navegador")
        print(" • Encontro de Mulas: Rendezvous central em x=55 com Loiter de 2.0s")
    print("=" * 65 + "\n")

    sim = builder.build()
    start_wall = time.time()
    sim.start_simulation()
    elapsed_wall = time.time() - start_wall

    METRICS.print_summary("DTN Multi-Mula (Arsheen et al.)")
    return {
        "scenario": "DTN Multi-Mula (Arsheen)",
        "pdr": (METRICS.data_delivered / METRICS.data_sent * 100) if METRICS.data_sent > 0 else 0,
        "latency": METRICS.delivery_latency,
        "rtt": METRICS.round_trip_time,
        "transmissions": METRICS.total_transmissions,
        "hops": METRICS.hops,
        "success": METRICS.mission_success,
        "wall_time": elapsed_wall
    }


# -------------------------------------------------------------------
# Cenário 3: Flooding Controlado (Lim & Kim, 2001)
# -------------------------------------------------------------------
def run_flooding(real_time: bool = True, enable_vis: bool = True) -> Dict[str, Any]:
    METRICS.reset()
    sim_config = SimulationConfiguration(duration=20.0, real_time=real_time)
    builder = SimulationBuilder(configuration=sim_config)

    medium = CommunicationMedium(transmission_range=42.0, delay=0.01)
    builder.add_handler(CommunicationHandler(communication_medium=medium))
    builder.add_handler(TimerHandler())
    builder.add_handler(MasslessMobilityHandler(MasslessMobilityConfiguration(default_speed=8.0)))

    if enable_vis:
        builder.add_handler(VisualizationHandler(configuration=create_vis_config(x_max=80.0, y_range=(-45.0, 45.0))))

    # Topologia em Malha Ramificada com Drones em Patrulha Ativa (Slide 12 de Lim & Kim 2001)
    builder.add_node(FloodingProtocol, (0.0, 0.0, 5.0))      # 0: Estação Base Terrestre
    builder.add_node(FloodingProtocol, (20.0, 15.0, 15.0))   # 1: Drone Relé Rota Norte (Em Patrulha)
    builder.add_node(FloodingProtocol, (20.0, -15.0, 15.0))  # 2: Drone Relé Rota Sul (Em Patrulha)
    builder.add_node(FloodingProtocol, (50.0, -25.0, 15.0))  # 3: Drone Periférico Sul (Ramo Extrâneo em Patrulha)
    builder.add_node(FloodingProtocol, (50.0, 25.0, 15.0))   # 4: Drone Alvo Nordeste (Target Zone em Patrulha)

    print("\n" + "=" * 65)
    print(" INICIANDO: FLOODING CONTROLADO (Lim & Kim, 2001)")
    print(" Topologia em Malha: Base (0) -> [Norte (1) & Sul (2)] -> Alvo (4) & Sul (3)")
    print(" Mobilidade: Drones 1, 2, 3 e 4 em patrulha ativa contínua de setor (8 m/s)")
    print(" Mecanismo: Difusão cega em todos os caminhos com descarte de duplicatas")
    if enable_vis:
        print(" • Visualizador 3D: https://project-gradys.github.io/gradys-sim-nextgen-visualization/")
        print(" • Observe todos os drones voando e retransmitindo simultaneamente")
    print("=" * 65 + "\n")

    sim = builder.build()
    start_wall = time.time()
    sim.start_simulation()
    elapsed_wall = time.time() - start_wall

    METRICS.print_summary("Flooding Controlado")
    return {
        "scenario": "Controlled Flooding",
        "pdr": (METRICS.data_delivered / METRICS.data_sent * 100) if METRICS.data_sent > 0 else 0,
        "latency": METRICS.delivery_latency,
        "rtt": METRICS.round_trip_time,
        "transmissions": METRICS.total_transmissions,
        "hops": METRICS.hops,
        "success": METRICS.mission_success,
        "wall_time": elapsed_wall
    }


# -------------------------------------------------------------------
# Cenário 4: GeoCast Protocol (Choi et al., 2018)
# -------------------------------------------------------------------
def run_geocast(real_time: bool = True, enable_vis: bool = True) -> Dict[str, Any]:
    METRICS.reset()
    sim_config = SimulationConfiguration(duration=20.0, real_time=real_time)
    builder = SimulationBuilder(configuration=sim_config)

    medium = CommunicationMedium(transmission_range=42.0, delay=0.01)
    builder.add_handler(CommunicationHandler(communication_medium=medium))
    builder.add_handler(TimerHandler())
    builder.add_handler(MasslessMobilityHandler(MasslessMobilityConfiguration(default_speed=8.0)))

    if enable_vis:
        builder.add_handler(VisualizationHandler(configuration=create_vis_config(x_max=80.0, y_range=(-45.0, 45.0))))

    # Mesma Topologia com Drones em Patrulha Ativa (Slide 13 & 14 de Choi et al. 2018)
    builder.add_node(GeoCastProtocol, (0.0, 0.0, 5.0))      # 0: Estação Base Terrestre
    builder.add_node(GeoCastProtocol, (20.0, 15.0, 15.0))   # 1: Drone Relé Norte (Forwarding Zone y>=0)
    builder.add_node(GeoCastProtocol, (20.0, -15.0, 15.0))  # 2: Drone Relé Sul (Fora da Zona -> Poda em Voo)
    builder.add_node(GeoCastProtocol, (50.0, -25.0, 15.0))  # 3: Drone Periférico Sul (Silenciado em Voo)
    builder.add_node(GeoCastProtocol, (50.0, 25.0, 15.0))   # 4: Drone Alvo Nordeste (Target Zone)

    print("\n" + "=" * 65)
    print(" INICIANDO: GEOCAST PROTOCOL (Choi et al., 2018)")
    print(" Topologia em Malha: Base (0) -> [Norte (1) aceita | Sul (2,3) descartam] -> Alvo (4)")
    print(" Mobilidade: Drones 1, 2, 3 e 4 em patrulha ativa contínua de setor (8 m/s)")
    print(" Mecanismo: Avaliação geográfica dinâmica com coordenadas GPS em tempo real")
    if enable_vis:
        print(" • Visualizador 3D: https://project-gradys.github.io/gradys-sim-nextgen-visualization/")
        print(" • Observe todos os drones voando, mas apenas a Rota Norte (1) transmitindo")
    print("=" * 65 + "\n")

    sim = builder.build()
    start_wall = time.time()
    sim.start_simulation()
    elapsed_wall = time.time() - start_wall

    METRICS.print_summary("GeoCast")
    return {
        "scenario": "GeoCast",
        "pdr": (METRICS.data_delivered / METRICS.data_sent * 100) if METRICS.data_sent > 0 else 0,
        "latency": METRICS.delivery_latency,
        "rtt": METRICS.round_trip_time,
        "transmissions": METRICS.total_transmissions,
        "hops": METRICS.hops,
        "success": METRICS.mission_success,
        "wall_time": elapsed_wall
    }


# -------------------------------------------------------------------
# Benchmark Comparativo Automático (Todos os 4 cenários em modo headless)
# -------------------------------------------------------------------
def run_benchmark_comparison() -> None:
    print("\n" + "=" * 75)
    print(" EXECUTANDO BENCHMARK COMPARATIVO ENTRE TODOS OS PROTOCOLOS")
    print(" (Executando em modo rápido headless / sem interface gráfica)")
    print("=" * 75)

    results: List[Dict[str, Any]] = []
    results.append(run_dtn_single_mule(real_time=False, enable_vis=False))
    results.append(run_dtn_multi_mule(real_time=False, enable_vis=False))
    results.append(run_flooding(real_time=False, enable_vis=False))
    results.append(run_geocast(real_time=False, enable_vis=False))

    print("\n" + "#" * 80)
    print("                    QUADRO COMPARATIVO DE DESEMPENHO")
    print("#" * 80)
    header = f"{'Protocolo':<26} | {'Sucesso':<8} | {'PDR (%)':<7} | {'Latência':<9} | {'RTT (s)':<8} | {'Transm.':<7} | {'Tempo Exec.':<10}"
    print(header)
    print("-" * 80)

    for r in results:
        status = "SIM" if r["success"] else "NÃO"
        pdr_s = f"{r['pdr']:.1f}%"
        lat_s = f"{r['latency']:.2f}s" if r['latency'] is not None else "N/A"
        rtt_s = f"{r['rtt']:.2f}s" if r['rtt'] is not None else "N/A"
        tx_s = str(r["transmissions"])
        wall_s = f"{r['wall_time']:.2f}s"
        print(f"{r['scenario']:<26} | {status:<8} | {pdr_s:<7} | {lat_s:<9} | {rtt_s:<8} | {tx_s:<7} | {wall_s:<10}")

    print("#" * 80 + "\n")


# -------------------------------------------------------------------
# Menu Principal Interativo e Suporte a Argumentos de Linha de Comando
# -------------------------------------------------------------------
def prompt_mode() -> Optional[Tuple[bool, bool]]:
    """
    Solicita e valida estritamente o modo de execução interativo.
    Retorna (real_time, enable_vis) ou None se o usuário cancelar/voltar.
    """
    while True:
        print("\nEscolha o modo de execução:")
        print("1 - Modo Visualizador 3D Web (Tempo Real com Browser)")
        print("2 - Modo Rápido Headless (Sem Browser, execução instantânea)")
        print("0 - Voltar ao Menu Principal")
        try:
            modo_input = input("Modo (1 ou 2, padrão 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperação cancelada.")
            return None

        if modo_input in ["", "1"]:
            return (True, True)
        elif modo_input == "2":
            return (False, False)
        elif modo_input == "0":
            return None
        else:
            print(f"\n[AVISO] Opção '{modo_input}' inválida! Digite apenas '1' para Visualizador 3D, '2' para Headless ou '0' para Voltar.")


def main() -> None:
    # 1. Tratamento quando argumentos CLI são passados (ex: python main.py 1 1 ou python main.py 5)
    if len(sys.argv) > 1:
        cli_opcao = sys.argv[1].strip()
        if cli_opcao not in ["1", "2", "3", "4", "5"]:
            print(f"\n[ERRO] Opção CLI '{cli_opcao}' inválida! Escolha um valor entre 1 e 5.")
            print("Uso: python main.py <cenario: 1-5> [modo: 1-2]")
            sys.exit(1)

        if cli_opcao in ["1", "2", "3", "4"]:
            cli_modo = sys.argv[2].strip() if len(sys.argv) > 2 else "1"
            if cli_modo not in ["1", "2"]:
                print(f"\n[ERRO] Modo CLI '{cli_modo}' inválido! Digite '1' (Visualizador 3D) ou '2' (Headless).")
                print("Uso: python main.py <cenario: 1-5> [modo: 1-2]")
                sys.exit(1)

            real_time = (cli_modo == "1")
            enable_vis = (cli_modo == "1")

            if cli_opcao == "1":
                run_dtn_single_mule(real_time=real_time, enable_vis=enable_vis)
            elif cli_opcao == "2":
                run_dtn_multi_mule(real_time=real_time, enable_vis=enable_vis)
            elif cli_opcao == "3":
                run_flooding(real_time=real_time, enable_vis=enable_vis)
            elif cli_opcao == "4":
                run_geocast(real_time=real_time, enable_vis=enable_vis)

        elif cli_opcao == "5":
            run_benchmark_comparison()

        return

    # 2. Modo Interativo com Menu e Validação em Loop
    while True:
        print("\n" + "=" * 55)
        print("  SIMULADOR DE PROTOCOLOS FANET / DTN (GrADyS-SIM NG)")
        print("=" * 55)
        print("Escolha o cenário de simulação:")
        print("1 - DTN Tradicional (1 Mula Móvel - Store-Carry-Forward)")
        print("2 - DTN Multi-Mula (Arsheen et al. - Cadeia de Rendezvous)")
        print("3 - Flooding Controlado (Lim & Kim - Descarte por TTL)")
        print("4 - GeoCast (Choi et al. - Delivery Zone Georreferenciada)")
        print("5 - Benchmark Comparativo Completo (Roda todos em modo rápido)")
        print("0 - Sair")

        try:
            opcao = input("\nOpção (0-5): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando simulador.")
            break

        if opcao == "0":
            print("\nEncerrando simulador.")
            break

        elif opcao in ["1", "2", "3", "4"]:
            modo_config = prompt_mode()
            if modo_config is None:
                continue

            real_time, enable_vis = modo_config

            if opcao == "1":
                run_dtn_single_mule(real_time=real_time, enable_vis=enable_vis)
            elif opcao == "2":
                run_dtn_multi_mule(real_time=real_time, enable_vis=enable_vis)
            elif opcao == "3":
                run_flooding(real_time=real_time, enable_vis=enable_vis)
            elif opcao == "4":
                run_geocast(real_time=real_time, enable_vis=enable_vis)

            try:
                input("\nPressione [ENTER] para retornar ao menu principal...")
            except (EOFError, KeyboardInterrupt):
                break

        elif opcao == "5":
            run_benchmark_comparison()
            try:
                input("\nPressione [ENTER] para retornar ao menu principal...")
            except (EOFError, KeyboardInterrupt):
                break

        else:
            print(f"\n[AVISO] Opção '{opcao}' inválida! Por favor, escolha um número de 0 a 5.")


if __name__ == "__main__":
    main()