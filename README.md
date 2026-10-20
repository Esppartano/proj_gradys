# T1 — Roteamento num Swarm Core em V (GrADySim)

Trabalho T1 da disciplina INF2541 (PUC-Rio). Compara quatro protocolos de
roteamento num enxame de drones simulado no [GrADySim](https://github.com/Project-GrADyS/gradys-sim-nextgen):

| Protocolo | Ideia |
|---|---|
| **Flooding** | Inundação por broadcast com TTL, *self-pruning* e ACK do receptor |
| **GeoCast** | Encaminhamento guloso até a zona-alvo e inundação local dentro dela |
| **DTN** | Store-carry-forward, com troca completa de mensagens a cada encontro |
| **SwCore** | Rota pela árvore geradora do Swarm Core, com tabela de alcance por destino (satélites e BS) |

Cenário: 9 drones em formação em V (o Core) girando em torno de uma estação base
(BS), e 4 satélites que se acoplam periodicamente ao V. Todos os protocolos
rodam com a mesma mobilidade e o mesmo tráfego.

Detalhes do cenário, das decisões de projeto, dos resultados e das
referências: **[RELATORIO.md](RELATORIO.md)**.

## Requisitos

- Python 3.11 (testado com 3.11.0)
- `gradysim==0.8.0` (em `requirements.txt`)

## Instalação

```powershell
py -3.11 -m venv gradys-env
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # libera o script de ativação só nesta janela
.\gradys-env\Scripts\Activate.ps1
pip install -r requirements.txt
```

`py -3.11` garante o Python 3.11 quando há mais de uma versão instalada. Sem
ativar o ambiente, dá para chamar o Python dele direto:
`.\gradys-env\Scripts\python.exe main.py`.

## Como rodar

```powershell
python main.py              # menu interativo
python main.py 5            # benchmark dos 4 protocolos, modo rápido (sem browser)
python main.py 4 1          # SwCore no visualizador 3D (abre o browser)
python main.py 3 2          # DTN em modo rápido
```

Formato dos atalhos: `python main.py <opção> [modo]`

| Opção | Protocolo |
|---|---|
| 1 | Flooding |
| 2 | GeoCast |
| 3 | DTN |
| 4 | SwCore |
| 5 | Benchmark (todos) |

Modo: `1` = visualizador 3D (padrão) · `2` = rápido, sem browser.

## Saídas

- **`results.md`**: tabela comparativa com a legenda de cada coluna. É gerada
  pelo benchmark (opção 5).
- **`logs/<protocolo>.log`**: eventos de cada execução (criação, repasse,
  entrega, conexão dos satélites…), um por linha. Fica fora do git.

### Cores no visualizador 3D

| Cor | Significado |
|---|---|
| Azul | BS |
| Roxo | C1, ápice e líder da formação |
| Branco | Demais nós do Core |
| Amarelo / laranja | Satélite em patrulha / em tandem com o hub |
| Marrom-claro | Nó carregando mensagens |
| Magenta / ciano / verde | Criou / repassou / recebeu mensagem |
| Vermelho | Descartou mensagem (TTL esgotado; no GeoCast, também sem rota) |
| Cinza-grafite | Podou a retransmissão por estar fora da zona-alvo (GeoCast) |
| Verde-claro / vermelho-claro | Anunciou alcance / perda de alcance de um satélite ou da BS (SwCore) |

O painel **Panel** (canto inferior direito) mostra o estado de cada nó. O
número é o ID: 0 = BS, 1–9 = C1–C9, 10–13 = S1–S4.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `main.py` | Menu e atalhos de linha de comando |
| `src/config.py` | Todos os parâmetros ajustáveis |
| `src/scenario.py` | Plano compartilhado: geometria do V, árvore, setores, tráfego |
| `src/node.py`, `src/nodes.py` | Camada comum (beacons, formação em cascata, handshake e tandem) e a montagem do nó de cada protocolo |
| `src/radio.py` | Alcance maior da BS |
| `src/routing/` | Um mixin por protocolo, mais a base comum e os formatos de mensagem |
| `src/metrics.py`, `src/motor.py` | Métricas, execução da simulação e tabela |
| `src/viz.py`, `src/eventlog.py` | Visualização 3D e log em arquivo |
