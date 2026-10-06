"""
Menu interativo do simulador (mesmo esquema do menu original).

Todos os protocolos rodam no mesmo cenário: Swarm Core em V
(torre + 9 Core + 4 satélites).

Uso, a partir da raiz do projeto:
    python main.py              # menu interativo
    python main.py 4 1          # atalho: protocolo 4 (Árvore Geradora) no visualizador 3D
    python main.py 3 2          # atalho: protocolo 3 (DTN) headless
    python main.py 5            # atalho: benchmark comparativo
"""
import logging
import sys
from typing import Optional

from src.main import print_table, run
from src.nodes import PROTOCOLS

SCENARIOS = {
    "1": ("Flooding (supressão de duplicatas + TTL)", "flooding"),
    "2": ("GeoCast (zona de encaminhamento geográfica)", "geocast"),
    "3": ("DTN (Store-Carry-Forward com custódia)", "dtn"),
    "4": ("Árvore Geradora (roteamento do Swarm Core)", "tree"),
}
BENCHMARK = "5"
USAGE = "Uso: python main.py <opcao: 1-5> [modo: 1-2]"


def run_scenario(option: str, viz: bool) -> None:
    _, protocol = SCENARIOS[option]
    print_table([{"protocol": protocol, **run(protocol, viz)}])


def run_benchmark() -> None:
    print("\nRodando os 4 protocolos em modo headless...\n")
    print_table([{"protocol": p, **run(p, viz=False)} for p in PROTOCOLS])


def prompt_mode() -> Optional[bool]:
    """Retorna True (visualizador 3D), False (headless) ou None (voltar)."""
    while True:
        print("\nEscolha o modo de execução:")
        print("1 - Modo Visualizador 3D Web (Tempo Real com Browser)")
        print("2 - Modo Rápido Headless (Sem Browser)")
        print("0 - Voltar ao Menu Principal")
        try:
            mode = input("Modo (1 ou 2, padrão 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperação cancelada.")
            return None

        if mode in ("", "1"):
            return True
        if mode == "2":
            return False
        if mode == "0":
            return None
        print(f"\n[AVISO] Opção '{mode}' inválida! Digite '1' para Visualizador 3D, '2' para Headless ou '0' para Voltar.")


def pause() -> bool:
    try:
        input("\nPressione [ENTER] para retornar ao menu principal...")
        return True
    except (EOFError, KeyboardInterrupt):
        return False


def main() -> None:
    # Logs INFO do GrADySim poluem a saída; os eventos de roteamento são impressos à parte.
    logging.disable(logging.INFO)

    # 1. Atalhos de linha de comando (ex: python main.py 4 1 ou python main.py 5)
    if len(sys.argv) > 1:
        option = sys.argv[1].strip()
        if option == BENCHMARK:
            run_benchmark()
            return
        if option not in SCENARIOS:
            print(f"\n[ERRO] Opção CLI '{option}' inválida! Escolha um valor entre 1 e 5.\n{USAGE}")
            sys.exit(1)
        mode = sys.argv[2].strip() if len(sys.argv) > 2 else "1"
        if mode not in ("1", "2"):
            print(f"\n[ERRO] Modo CLI '{mode}' inválido! Digite '1' (Visualizador 3D) ou '2' (Headless).\n{USAGE}")
            sys.exit(1)
        run_scenario(option, viz=(mode == "1"))
        return

    # 2. Menu interativo
    while True:
        print("\n" + "=" * 60)
        print("  SIMULADOR DE PROTOCOLOS FANET / DTN (GrADyS-SIM NG)")
        print("  Cenário: Swarm Core em V (Torre + 9 Core + 4 Satélites)")
        print("=" * 60)
        print("Escolha o protocolo de roteamento:")
        for key, (name, _) in SCENARIOS.items():
            print(f"{key} - {name}")
        print(f"{BENCHMARK} - Benchmark Comparativo (todos, modo rápido)")
        print("0 - Sair")

        try:
            option = input("\nOpção (0-5): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando simulador.")
            break

        if option == "0":
            print("\nEncerrando simulador.")
            break
        elif option in SCENARIOS:
            viz = prompt_mode()
            if viz is None:
                continue
            run_scenario(option, viz)
            if not pause():
                break
        elif option == BENCHMARK:
            run_benchmark()
            if not pause():
                break
        else:
            print(f"\n[AVISO] Opção '{option}' inválida! Por favor, escolha um número de 0 a 5.")


if __name__ == "__main__":
    main()
