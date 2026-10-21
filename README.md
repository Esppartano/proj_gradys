# T1 — Roteamento Swarm Core em Topologia V (GrADySim)

T1 da disciplina INF2541 (PUC-Rio). Compara quatro protocolos de
roteamento num enxame de drones simulado no [GrADySim](https://github.com/Project-GrADyS/gradys-sim-nextgen):

| Protocolo | Ideia |
|---|---|
| **Flooding** | Inundação por broadcast com TTL, *self-pruning* e ACK do receptor |
| **GeoCast** | Encaminhamento guloso até a zona-alvo, busca de rota para contornar vazios e inundação local dentro da zona |
| **DTN** | Store-carry-forward, com troca completa de mensagens a cada encontro |
| **SwCore** | Rota pela árvore geradora do Swarm Core, com tabela de alcance por destino (cada satélite) |

Cenário: 9 drones em formação em V (o Core), a 20 m uns dos outros, girando em
torno do próprio centro (uma volta por minuto), e 4 satélites nos eixos leste,
norte, oeste e sul, que esperam no ponto de acoplamento, acoplam quando uma das
pontas do V passa, trocam mensagens, se afastam pelo próprio eixo e retornam.
Rádio de 30 m.
Todos os protocolos rodam com a mesma mobilidade e o mesmo tráfego.

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
python main.py 5            # benchmark dos 4 protocolos, modo rápido (sem browser, ≈ 10 s)
python main.py 4 1          # SwCore no visualizador 3D (abre o browser; tempo real)
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

A simulação cobre 10 voltas (10 min simulados). No visualizador 3D, que roda
em tempo real, uma volta leva 1 min; para encerrar antes, use Ctrl+C.

## Saídas

- **`results.md`**: tabela comparativa com a legenda de cada coluna. É gerada
  pelo benchmark (opção 5).
- **`logs/<protocolo>.log`**: eventos de cada execução (criação, repasse,
  entrega, conexão dos satélites…), um por linha. Fica fora do git.

### Cores no visualizador 3D

| Cor | Significado |
|---|---|
| Roxo | C1, ápice e líder da formação |
| Branco | Demais nós do Core |
| Amarelo / laranja | Satélite esperando ou se deslocando / acoplado, trocando mensagens |
| Marrom-claro | Nó carregando mensagens |
| Magenta / ciano / verde | Criou / repassou / recebeu mensagem |
| Vermelho | Descartou mensagem (TTL esgotado; no GeoCast, também sem rota) |
| Cinza-grafite | Podou a retransmissão: todos os vizinhos já ouviram (Flooding) ou fora da zona-alvo (GeoCast) |
| Verde-claro / vermelho-claro | Anunciou alcance / perda de alcance de um satélite (SwCore) |

O painel **Panel** (canto inferior direito) mostra o estado de cada nó. O
número é o ID: 0–8 = C1–C9, 9–12 = S1–S4.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `main.py` | Menu e atalhos de linha de comando |
| `src/config.py` | Todos os parâmetros ajustáveis |
| `src/scenario.py` | Plano compartilhado: geometria do V, árvore, eixos e pontos de acoplamento |
| `src/node.py`, `src/nodes.py` | Camada comum (beacons, formação em cascata, handshake e ciclo dos satélites) e a montagem do nó de cada protocolo |
| `src/pacing.py` | Ritmo acelerado do modo 3D |
| `src/routing/` | Um mixin por protocolo, mais a base comum e os formatos de mensagem |
| `src/metrics.py`, `src/motor.py` | Métricas, execução da simulação e tabela |
| `src/viz.py`, `src/eventlog.py` | Visualização 3D e log em arquivo |
