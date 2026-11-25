# Relatório — T2: Pub/Sub distribuído sobre o SwCore

**Disciplina:** INF2541 · **Simulador:** GrADySim 0.8.0

---

## 1. Objetivo

Implementar e avaliar um sistema **Publish/Subscribe distribuído** para o enxame
em V do T1, em duas camadas, como pede o enunciado:

| Camada | Papel | Origem |
|---|---|---|
| **SwCore Routing** | Roteamento em múltiplos saltos, alcançabilidade dos satélites e armazenamento até a reconexão | SwCore **fornecido pelo professor**, implementado no repositório [routing-ricardo](https://github.com/INF2541-Intro-Mobile-Ubiquous-Computing/routing-ricardo) (Ricardo Leta), reutilizado sem alterar a lógica |
| **Pub/Sub distribuído** | Tópicos, assinaturas e filtros; decidir quem deve receber e pedir o encaminhamento ao SwCore, sem que o publicador conheça os assinantes | Implementação deste trabalho (`src/pubsub.py`) |

Requisitos atendidos:

- os 13 nós (Core e satélites) assinam os tópicos fixos **T1** e **T2** ao
  longo da missão; o Core publica ao acaso e os satélites publicam ao encontrar
  sensores (par → T2, ímpar → T1);
- **filtro pela região de origem**: N, E, S, W (eixo do satélite) ou C (Core);
- **fila do tópico**: quem assina recebe todas as mensagens do tópico desde a
  criação, respeitando o filtro; ao voltar e pedir de novo, só as não lidas;
- **3 PSPeers** afastados e distribuídos no V, com cópias completas;
- **sincronização por multicast**, sem retransmissão;
- **falha de core**: a cada 30 s, um nó do Core sorteado fica incomunicável
  por 1 s, e as rotas são refeitas para pular o nó;
- sem ACKs nem tolerância a falhas obrigatórias: perda admitida.

---

## 2. Cenário

O Core é o do T1 ([RELATORIO.md](RELATORIO.md)): 9 nós em V a 20 m, uma volta
por minuto em torno do próprio centro, rádio de 30 m. O T2 muda os satélites e
acrescenta sensores. Essas mudanças valem **só na opção 6** do menu; os
protocolos do T1 (opções 1–5) rodam no cenário do T1, sem satélites afastados
nem sensores. A falha de core, ligada por padrão nesta branch, vale para todos.

| Elemento | T2 |
|---|---|
| **Satélites** | Começam afastados (113,6 m do centro), no eixo de cada lado: S1 leste e S3 oeste se movem na horizontal, S2 norte e S4 sul na vertical. Aproximam-se em linha reta, esperam no limite da área varrida pelo Core (ponto de acoplamento, 73,6 m do centro, 5 m além do raio varrido de 68,6 m), acoplam na ponta do V que passa, trocam mensagens por 2 s e se afastam de novo. |
| **Sensores** (`src/sensor.py`) | 12 nós fixos, 3 por eixo, entre o ponto de acoplamento e o de afastamento (+8, +22 e +36 m, com desvio lateral de 6 m). IDs 13 a 24, consecutivos em cada eixo, então há sensor par e ímpar em todos os eixos. Cada sensor gera uma leitura a cada 5 s e a entrega ao satélite que passa. |
| **Falha de core** | Em t = 30, 60, 90… s, um nó do Core sorteado (semente fixa) não transmite nem recebe nada durante 1 s. Nenhum nó sabe da falha de outro: os vizinhos só deixam de ouvi-lo. O próprio nó só sabe que o seu rádio voltou (seção 3). |
| **Duração** | 60 min simulados. As duas últimas voltas só entregam o que está pendente, porque a publicação de um satélite espera nele até o acoplamento. |

---

## 3. SwCore do professor (`src/routing/swcore_professor.py`)

O arquivo é uma cópia do `src/swcore_mixin.py` do repositório routing-ricardo
(commit `98392c1`). Só os imports mudaram, para apontar para os módulos deste
projeto. O que o código espera do nó é fornecido por
`src/routing/professor_adapter.py`.

| Função | Como o SwCore do professor faz |
|---|---|
| **RT para os satélites** | Linha por satélite (`direct`, próximo salto ou `unreachable`), com versão. Conectar/desconectar gera uma atualização inundada pelo Core; cópias da mesma versão por outros vizinhos viram caminhos alternativos. |
| **RT para o Core** | *Path vector* nos beacons: cada nó anuncia o caminho até cada outro nó do Core e monta os seus a partir dos vizinhos ouvidos há até 0,4 s. Mudou um caminho, beacon na hora. |
| **PSPeer mais próximo** | `nearest_pspeer()`: o PSPeer com o caminho mais curto na RT do Core. |
| **Armazenamento** | Mensagem para satélite sem rota fica no `_core_buffer` e é tentada de novo a cada 0,25 s e quando chega um "alcançável". |
| **Volta da falha** | `on_comm_restored()`: o nó pede aos vizinhos as linhas de satélite que perdeu. |

**Integração** (no adaptador e em `src/node.py`, sem tocar no código do professor):

- **Limite de saltos:** `SWCORE_MAX_HOPS` = 10, contra 8 no original. De
  ponta a ponta, o V tem 8 saltos, mais o upload e a entrega ao satélite.
- **Volta da falha** (bug achado no passo de testes de falha, seção 5): logo
  após a falha, o nó ainda não ouviu os vizinhos, porque todos ficaram
  "velhos". O que ele pedia ou detectava nesse instante, como um satélite que
  saiu durante a falha, era repassado a ninguém. Por isso:
  - o aviso de volta (`on_comm_restored`) só sai depois de um ciclo de
    beacons mais uma margem (0,2 + 0,05 s);
  - o nó reanuncia as suas linhas de satélite com a mesma versão.

---

## 4. Pub/Sub (`src/pubsub.py`)

### 4.1 PSPeers

**C1, C4 e C8:** o líder e o 3º nó de cada asa. PSPeers vizinhos ficam a 3
saltos, e o V se divide em 3 grupos iguais, cada nó a no máximo 1 salto do
seu PSPeer.

| Nó | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
|---|---|---|---|---|---|---|---|---|---|
| PSPeer mais próximo | C1 | C1 | C4 | C4 | C4 | C1 | C8 | C8 | C8 |

Cada PSPeer guarda a **fila de cada tópico** (todas as publicações, em ordem de
criação) e todas as **assinaturas** (assinante, tópico, filtro). Os demais nós
do Core não guardam estado de Pub/Sub.

### 4.2 Clientes

| Quem | Assina | Publica |
|---|---|---|
| **Nó do Core** (região C) | A cada 5 s, 1% de chance de assinar um tópico que ainda não assina, com filtro sorteado (subconjunto não vazio de {N, E, S, W, C}) | A cada 5 s, 20% de chance, tópico sorteado |
| **Satélite** (região do eixo) | Igual; a assinatura feita longe do Core vai no próximo acoplamento | Ao **encontrar um sensor**: sensor par → T2, ímpar → T1. Uma publicação por sensor a cada viagem (entre dois desacoplamentos). A publicação nasce no encontro e espera no satélite até ele acoplar. |

Cada nó assina cada tópico no máximo uma vez, com filtro fixo.

### 4.3 Entrega

| Assinante | Como recebe |
|---|---|
| **Nó do Core** | O PSPeer que recebeu a assinatura dele vira o seu **PSPeer de casa**. Ao receber a assinatura, a casa manda a fila do tópico desde a criação, num lote, em ordem; depois, cada publicação nova que chega à sua fila (do cliente ou por sync). Cada par (assinante, publicação) tem um só remetente. |
| **Satélite** | Ao acoplar, **solicita** as não lidas ao PSPeer mais próximo do hub, enviando as suas assinaturas e o que já leu. O PSPeer responde com as publicações da fila que passam no filtro e ainda não foram lidas. A resposta vai pelo SwCore do professor, que a guarda no Core se o satélite já tiver saído. |

### 4.4 Mensagens

| Mensagem | Caminho |
|---|---|
| `pubsub` | Cliente → PSPeer mais próximo (pedido de assinatura, publicação ou solicitação) e PSPeer de casa → assinante do Core. Salto a salto pela RT do Core do professor (`next_hop_core`). O pedido de satélite vai ao hub, que escolhe o PSPeer mais próximo dele. |
| `pubsub_sync` | PSPeer → todo o Core (multicast, seção 4.5) |
| `routing_swcore` e `dock_deliver` | PSPeer → satélite, pelo SwCore do professor (`_core_buffer` e `_route`): `routing_swcore` entre nós do Core, `dock_deliver` do hub ao satélite |

- **Sem ACK.** Sem rota (vizinho em falha, PSPeer inalcançável), a mensagem
  espera no nó e é tentada de novo a cada 0,25 s. As seguintes para o mesmo
  destino esperam atrás dela, para não a ultrapassar.
- **Lote por viagem.** As publicações de uma viagem de satélite vão num só
  pacote, do satélite até o assinante (hub, PSPeer, sync e entrega). O GrADySim não garante a ordem de dois
  pacotes enviados no mesmo instante: a fila de eventos compara só o horário
  (`Event.__lt__` em `gradysim/simulator/event.py`), e o `heapq` não é
  estável. Enviadas uma a uma, publicações da mesma viagem chegavam
  invertidas (146 em 20 min).

### 4.5 Sincronização

Cada mudança que um PSPeer recebe de um cliente vira um `pubsub_sync`. A
mudança pode ser uma assinatura nova ou as publicações novas: as cópias são
completas, de tópicos e de assinaturas.

- **Multicast:** o rádio do Core só alcança os vizinhos da árvore, então o
  multicast é uma inundação. Cada nó do Core repassa cada sync uma vez (a
  ponta do V não o devolve). PSPeers guardam a mudança; os demais nós
  repassam e descartam.
- **Sem retransmissão:** um sync que cruza um nó em falha se perde para o
  outro lado do V. Com o PSPeer de casa, isso custa só aquela mudança: os
  assinantes daquele PSPeer não recebem aquela publicação, e um satélite pode
  recebê-la de outro PSPeer ao solicitar.

---

## 5. Falha e reconstrução das rotas

Medido nas 119 falhas de 60 min, com scripts de verificação à parte (as
métricas de recuperação da seção 6 entram na tabela):

- **Exclusão:** o nó em falha some das rotas de todos os outros em média
  0,31 s (máximo 0,6 s): é o timeout de vizinho, de 0,4 s, mais a
  propagação.
- **Pular o nó:** o V é uma árvore, sem caminho físico alternativo. "Pular" é
  trocar de PSPeer quando possível:

| Nó em falha | Efeito |
|---|---|
| C1 | C2 passa a usar C4 (via C3); C6 passa a usar C8 (via C7) |
| C4 | C3 passa a usar C1; C5 fica 1 s sem PSPeer (os pedidos esperam) |
| C8 | C7 passa a usar C1; C9 fica 1 s sem PSPeer |

- **Fases das falhas:** como a volta dura 60 s e a falha começa em múltiplos
  de 30 s, os acoplamentos caem sempre nas mesmas fases. No cenário padrão,
  nenhum acoplamento cruza uma falha (0 de 480 no cenário do T1; 0 de 479 no do
  T2). Para testar falhas durante
  acoplamentos, `FAILURE_OFFSET` (em `src/config.py`) desloca as falhas.
  Foi assim que apareceu o bug da seção 3: em cerca de 90 das 119 falhas, as
  linhas de satélite ficavam erradas por mais de 10 s. Depois da correção,
  119/119 se acertam em todos os deslocamentos testados (0; 1,5; 3,3; 3,5;
  10,5; 12,5; 13,7 s).

---

## 6. Métricas

Definidas em `src/pubsub.py` (`PubSubMetrics`), sobre um gabarito global:
o assinante *s* deve receber a publicação *p* se assina o tópico de *p* com
filtro que contém a região de *p* e não é o autor. Isso vale **inclusive** para
publicações anteriores à assinatura (fila desde a criação).

| Métrica do enunciado | Definição adotada |
|---|---|
| **MDR** | % das publicações que chegaram a **todos** os assinantes elegíveis. Só entram publicações com ao menos um elegível. A taxa por par (assinante, publicação) vai à parte. |
| **Fora de ordem** | % das entregas que chegam depois de uma publicação mais nova do mesmo autor, no mesmo tópico, para o mesmo assinante. As filas de tópicos diferentes são independentes. |
| **Latência ponta a ponta** | Da publicação à entrega (média, p95 e p99), só para publicações **posteriores** à assinatura. A fila antiga mediria a idade do tópico, não a notificação; ela é medida da assinatura à entrega, à parte. |
| **Recuperação após falha** | Do fim da falha até, ao mesmo tempo, todo o Core ter rota aos outros 8 nós, o mesmo PSPeer mais próximo de antes e as linhas de satélite iguais ao estado real. Amostrada na verificação de RT que C1 já faz a cada 0,1 s (nenhum evento a mais; um evento extra muda a ordem dos simultâneos no GrADySim). Acima de 10 s, conta como não recuperada. O estado das assinaturas tem métricas próprias: convergência e assinaturas nunca sincronizadas. |

Energia não é pedida no T2: fica fora das métricas do enunciado e é medida à
parte, por nó (seção 7.1).

---

## 7. Resultados

Gerados por `python main.py 6 2` (60 min, `results_pubsub.md`). A coluna "sem
falha" usa `CORE_FAILURE = False`, com a mesma carga.

| Métrica | Com falha | Sem falha |
|---|---|---|
| **MDR** | **97,67%** | **100%** |
| **Fora de ordem** | **0,12%** | **0%** |
| **Latência média / p95 / p99** | **19,10 / 41,15 / 61,95 s** | **18,86 / 41,15 / 61,95 s** |
| **Recuperação após falha (média / máx.)** | **0,19 / 0,30 s** (119/119) | — |
| Publicações (Core / satélites) | 2616 (1218 / 1398) | 2616 (1218 / 1398) |
| Assinaturas | 26 | 26 |
| Entregas esperadas / entregues | 22241 / 22059 | 22241 / 22241 |
| Taxa por par | 99,18% | 100% |
| Falsos positivos / duplicadas | 0 / 0 | 0 / 0 |
| Entregas ao vivo / da fila antiga | 17377 / 4682 | 17522 / 4719 |
| Latência da fila antiga (desde a assinatura) | 6,88 s | 6,74 s |
| Saltos médios | 5,35 | — |
| Convergência de assinatura | 5,28 s (0 não sincronizadas) | — |
| Tx dados / Tx controle | 9811 / 21190 | 9862 / 19634 |

**Latência ao vivo por tipo** (com falha):

| Assinante ← autor | Entregas | Média | p95 | Saltos |
|---|---|---|---|---|
| Core ← Core | 4799 | 0,04 s | 0,07 s | 3,94 |
| Core ← satélite | 7920 | 26,44 s | 32,18 s | 5,71 |
| Satélite ← Core | 2842 | 16,01 s | 33,14 s | 5,65 |
| Satélite ← satélite | 1816 | 42,24 s | 62,13 s | 7,36 |

**Falhas durante acoplamentos** (`FAILURE_OFFSET = 3,5`, 20 min): recuperação
de 0,67 s em média, máximo 2,9 s, 39/39.

**Exemplo** (`p11_31`, com falha): em 300,1 s, S3 (oeste) passa pelo sensor
X19 (ímpar) e publica em T1. A publicação espera em S3 até o acoplamento e
chega a C3 e C5 em 332,0 s (31,9 s, quase todo de espera no satélite). Os
outros assinantes elegíveis a recebem pela fila antiga, quando assinam:

- C6, C2, C7, C8 e C4 a recebem em menos de 0,1 s após assinar;
- S2 assinou já acoplado (521,5 s): a assinatura disparou uma nova solicitação,
  e a resposta chegou no mesmo acoplamento (521,6 s);
- S1 e S4 assinaram longe do Core e a receberam no acoplamento seguinte.

### 7.1 Energia (extra, não exigida pelo enunciado)

Medida para uso futuro (gestão de energia do enxame), sem entrar nas métricas
do enunciado. Está em `results_pubsub.md`, por papel e por nó.

**Critério de medição** (`src/metrics.py`):

| Gasto | Como é medido | Unidade |
|---|---|---|
| **Comunicação** | Cada pacote transmitido pelo nó conta 1 (`E_TX`) e cada pacote recebido conta 0,5 (`E_RX`). Um broadcast conta uma recepção por ouvinte; um unicast só chega ao destinatário (o GrADySim não o entrega a terceiros ao alcance). O nó em falha não transmite nem recebe. A contagem é feita na entrada e na saída do rádio de cada nó, antes de qualquer protocolo, e não cria eventos. | Relativa (a mesma do T1), não joules |
| ↳ protocolo | Pub/Sub e SwCore: pedidos, entregas, syncs, RT de satélites, confirmações de upload | |
| ↳ enlace | Beacons (periódicos e disparados por mudança de rota) e handshake de acoplamento (`link*`). No SwCore do professor, os beacons do Core levam a RT do Core. No T1, ficavam fora da energia. | |
| ↳ coleta | Leituras entregues pelos sensores aos satélites (`sensor_data`) | |
| **Voo** | Distância = soma dos deslocamentos entre telemetrias consecutivas (a cada 0,05 s). Tempo em movimento = soma dos intervalos com deslocamento > 1 mm. Sem coeficientes físicos, porque o gasto por metro depende do drone. | m, s |

**Por papel** (média por nó, 60 min, com falha):

| Papel (nós) | E protocolo | E enlace | E coleta | E total | Tx / Rx protocolo | Distância | Em movimento |
|---|---|---|---|---|---|---|---|
| PSPeer (3) | 7122 | 38305 | 0 | 45427 | 5119 / 4006 | 15,8 km | 3596 s |
| Core, não PSPeer (6) | 4988 | 35000 | 0 | 39988 | 2458 / 5062 | 15,5 km | 3595 s |
| Satélite (4) | 436 | 21982 | 900 | 23319 | 225 / 422 | 9,6 km | 1914 s |
| Sensor (12) | 1 | 7872 | 600 | 8473 | 0 / 1 | 0 | 0 |

- **O enlace domina a comunicação:** 81–91% da energia de rádio de cada nó do Core
  é de enlace, quase toda dos beacons a cada 0,2 s, que levam a RT do Core (o
  resto são beacons disparados por mudança de rota, beacons de satélites ouvidos
  pelas pontas e o handshake de acoplamento).
- **Ser PSPeer custa:**
  - **Energia de protocolo:** cerca de 43% a mais que nos demais nós do Core (7122 contra 4988).
  - **Energia total:** cerca de 14% a mais (45427 contra 39988).
  - **Distribuição do custo:** o PSPeer transmite mais (respostas, entregas e syncs: 5119 transmissões contra 2458), enquanto os nós internos de repasse (C2, C3, C6, C7) recebem mais, porque ouvem os dois lados do sync. As pontas C5 e C9 são os nós do Core que menos gastam.
- **Voo:**
  - **Core:** está sempre em movimento, girando. A distância cresce com o raio de rotação: C2 e C6 andam 8,1 km; as pontas C5 e C9, 25,9 km.
  - **Satélites:** passam 53% do tempo em movimento (o resto, esperando ou acoplados) e percorrem cerca de 9,6 km.

---

## 8. Discussão

- **Onde se perde (MDR 97,67%):**
  - **Publicações do Core:** 94,99% chegam a todos.
    - **Mecanismo provável** (não separei as perdas por causa): uma publicação feita durante uma falha não atravessa o nó caído. O pedido ao PSPeer pode ir para o vizinho em falha antes de a rota ser refeita (até 0,4 s), ou o sync se perde do outro lado do V.
  - **Publicações de satélites:** 100% chegam a todos.
    - **Causa:** efeito do cenário, não do protocolo. Os satélites só entregam ao acoplar, e no cenário padrão nenhum acoplamento coincide com uma falha (seção 5).
  - **Sem falha:** MDR de 100%, sem falsos positivos e sem duplicatas.
- **A latência é dos satélites, não do Pub/Sub:**
  - **Entre nós do Core:** 0,04 s.
  - **Com satélites:** a mensagem espera o satélite autor voltar (até ~32 s) e/ou o satélite assinante acoplar.
  - **Satélite → satélite:** soma as duas esperas (42 s em média).
  - **p99 (62 s):** são esses casos.
  - **Conclusão:** com rádio de 30 m e satélites que só falam acoplados, nenhum desenho entrega antes do acoplamento.
- **Fora de ordem:**
  - **Sem falha, 0%:** o lote por viagem e a fila em ordem de criação garantem a ordem.
  - **Com falha, 0,12%:** uma publicação cujo sync se perdeu chega depois por outro caminho (outro PSPeer, numa solicitação de satélite). É o efeito de "roteamento alterado durante a propagação" que o enunciado descreve.
- **Recuperação de 0,19 s:**
  - **O que domina:** o tempo de os vizinhos voltarem a se ouvir e trocarem caminhos nos beacons.
  - **Falha durante acoplamento (até 2,9 s):** o hub que volta ainda ouve, por alguns segundos, o satélite que saiu durante a falha. A linha "direct" só cai quando ele sai do alcance. A entrega não se perde, porque o satélite ainda está ao alcance e aceita.
- **Custo:**
  - **Controle:** o sync domina, com 11747 dos 21190 pacotes. Cada mudança percorre o Core inteiro, em cerca de 7 transmissões. É o preço de manter 3 cópias completas sem retransmissão.
  - **Dados:** o PSPeer de casa fica a ≤ 1 salto dos assinantes do Core.
- **PSPeer de casa × dono da publicação** (medido antes dos sensores, mesma carga do Core):
  - **Desenho alternativo:** o PSPeer que recebe a publicação a empurra.
  - **Prós do alternativo:** sobrevive melhor a uma falha no momento da publicação (MDR 99,43% contra 98,65%).
  - **Contras do alternativo:**
    - um único sync de assinatura perdido deixava o assinante sem as publicações dos outros PSPeers até o fim (MDR 95,62% contra 99,32% com falhas deslocadas);
    - gastava 3,3 vezes mais pacotes de dados.
  - **Escolha:** a casa, porque não fica presa a uma perda e porque a métrica de recuperação do enunciado pede "sincronizar os estados de assinatura".

---

## 9. Testes funcionais (`tests/test_pubsub.py`)

`python -m unittest tests.test_pubsub -v`: 6 testes, cerca de 10 s. Cada um
roda 150 s simulados sem falha, com as assinaturas e publicações aleatórias
desligadas e um roteiro fixo.

| Teste | Roteiro | Verifica |
|---|---|---|
| TF01 | C3 assina T1 {C}; C7 publica | C3 recebe |
| TF02 | C3, C9 e S1 assinam T2; C5 publica | os três recebem |
| TF03 | C3 assina T1 {N, S}; C9 assina T1 {C}; C7 publica | C3 não recebe; C9 (controle) recebe |
| TF04 | C8 e S2 assinam T1; C2 publica | os dois recebem |
| TF05 | C6 assina T2 {E} aos 40 s | recebe o que S1 publicou antes (sensor par) |
| TF06 | S3 assina T1; C2 publica aos 5 e aos 45 s | 1º acoplamento: só a 1ª; S3 longe aos 45 s; 2º acoplamento: só a 2ª; depois, nada |

Todos verificam também que ninguém recebeu nada indevido nem em dobro. Os
testes pegam erros de propósito: com o PSPeer ignorando o filtro ao entregar
aos assinantes do Core, TF01–TF05 falham; ignorando a lista de lidas, TF02, TF04
e TF06 falham.

---

## 10. Decisões de projeto e premissas

| Ponto do enunciado | Decisão |
|---|---|
| "SwCore fornecido pelo professor, só reutilizar" | Cópia do arquivo original; integração num adaptador, sem mudar a lógica |
| "Multicast de sincronização [...] sem retransmissão" | Inundação pelo Core, cada nó repassa uma vez; sem reenvio nem ACK |
| "Mudanças (novas assinaturas)" e "cópias completas dos tópicos e assinaturas" | O sync leva assinaturas e publicações novas |
| "Recebe todas as mensagens da fila desde que foi criado" | Fila completa ao assinar; gabarito e latência tratam a fila antiga à parte |
| "Ao retornar e solicitar, só as não lidas" | O satélite solicita a cada acoplamento, com a lista do que já leu |
| "Encontrar um sensor" | Uma vez por sensor a cada viagem; os sensores perto do ponto de acoplamento ficam ao alcance durante a espera |
| Momento da publicação do satélite | O encontro com o sensor; a latência inclui o tempo até acoplar |
| Filtros | Um por (assinante, tópico), sorteado e fixo |
| Não há tolerância a falhas obrigatória | A mensagem espera rota no nó (até o vizinho voltar), mas o que é enviado a um nó em falha se perde |

---

## 11. Como reproduzir

```bash
python main.py 6 2                     # 60 min sem browser: results_pubsub.md e logs/pubsub.log
python main.py 6 1                     # visualizador 3D (30× mais rápido)
python -m unittest tests.test_pubsub -v
```

- **Sem falha:** `CORE_FAILURE = False` em `src/config.py`.
- **Falhas durante acoplamentos:** `FAILURE_OFFSET` em `src/config.py` (ex.: 3,5).
- **Visualizador:**
  - o nó em falha fica vermelho-escuro;
  - os sensores aparecem em azul (par, T2) e verde-oliva (ímpar, T1);
  - o painel do nó do Core mostra o caminho até o PSPeer mais próximo.

## 12. Estrutura do código (T2)

| Arquivo | Conteúdo |
|---|---|
| `src/pubsub.py` | Clientes, PSPeers (fila, assinaturas, casa, sync), transporte no Core e métricas |
| `src/routing/swcore_professor.py` | SwCore do professor (cópia do routing-ricardo) |
| `src/routing/professor_adapter.py`, `src/routing/dock_protocol.py` | Integração do SwCore do professor ao nó deste projeto |
| `src/sensor.py` | Sensores par/ímpar |
| `src/scenario.py` | PSPeers, sensores, falha de core, região de cada nó |
| `src/node.py` | Ciclo dos satélites (começando afastados no T2), corte do rádio na falha, aviso de volta |
| `src/motor.py`, `main.py` | Opção 6 do menu e tabela `results_pubsub.md` (com a seção de energia) |
| `src/metrics.py` | Energia por nó: contagem por classe de pacote e voo (critério na seção 7.1) |
| `tests/test_pubsub.py` | TF01–TF06 |

## 13. Referências

- Enunciado do T2 e slides da disciplina INF2541 (Swarm Core, Pub/Sub
  distribuído e métricas de avaliação).
- SwCore fornecido pelo professor: repositório
  [INF2541-Intro-Mobile-Ubiquous-Computing/routing-ricardo](https://github.com/INF2541-Intro-Mobile-Ubiquous-Computing/routing-ricardo),
  Ricardo Leta, `src/swcore_mixin.py`, commit `98392c1`.
