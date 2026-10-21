# Relatório — T1: Roteamento Swarm Core em Topologia V

**Disciplina:** INF2541 · **Simulador:** GrADySim 0.8.0

---

## 1. Objetivo e hipótese

Comparar três métodos clássicos de roteamento em Flying Ad-Hoc Network (FANETs) — **DTN**, **Flooding** e
**GeoCast** — com o **SwCore**, que roteia pela árvore geradora de um *Swarm Core*.

**Hipótese:** o SwCore é

- **mais eficiente:** menos saltos redundantes, menos transmissões, menor atraso
  fim a fim e menos energia. A premissa é que roteamento estruturado custa
  muito menos que transmissões redundantes, que por sua vez custam menos que
  mover nós;
- **mais eficaz:** maior taxa de entrega (PDR).

---

## 2. Cenário

Um único cenário para todos os protocolos: **mesma mobilidade e mesmo tráfego**.
Só o protocolo de roteamento muda. Os parâmetros seguem as convenções da
disciplina, para permitir comparar as formações entre os trabalhos.

### 2.1 Nós

| IDs | Papel | Descrição |
|---|---|---|
| 0–8 | Core | Formação em V: C1 no ápice, C2–C5 na asa direita, C6–C9 na asa esquerda (z = 10 m) |
| 9–12 | Satélites | S1 (leste), S2 (norte), S3 (oeste) e S4 (sul), z = 12 m |

### 2.2 Geometria do Core

| Parâmetro | Valor | Motivo |
|---|---|---|
| Distância entre vizinhos diretos (L) | 20 m | Convenção da disciplina |
| Alcance do rádio | 30 m | Convenção da disciplina (Core e satélites) |
| Abertura de cada asa | 55° | Nós de asas opostas ficam a ≥ 2·L·sen(55°) ≈ 32,8 m, fora do alcance: no Core, só os vizinhos da árvore se ouvem |
| Rotação | 1 volta a cada 60 s (60 unidades de simulação), em torno do próprio centro (centroide do V) | Convenção da disciplina (velocidade angular constante); as pontas andam a ≈ 7,2 m/s |
| Extremidades | As duas pontas, C5 e C9, a 68,6 m do centro | Simétricas em relação ao eixo do V; o ápice fica a 25,5 m |
| Árvore geradora | As 8 arestas do V | C1–C2–C3–C4–C5 e C1–C6–C7–C8–C9 |

**Rigidez medida** (SwCore, 60 voltas): arestas da árvore entre **19,90 e 20,10 m**;
pares não vizinhos sempre a **≥ 32,76 m**, fora do alcance de 30 m.

### 2.3 Satélites

Cada satélite fica no seu eixo (E, N, W, S), parado no **ponto de
acoplamento**: 5 m além do perímetro varrido pela formação, isto é, a
73,6 m do centro. Ciclo de cada satélite:

1. **Espera:** parado no ponto de acoplamento. Descobre os nós do Core pelo
   rádio (30 m).
2. **Acoplamento:** acopla no nó do Core que passa pelo ponto (a até 10 m:
   uma das pontas do V), que vira o **hub**, e confirma com
   `link_req`/`link_ack`. Ao acoplar, cria uma mensagem para o satélite do
   eixo oposto.
3. **Troca:** fica acoplado por 2 s, enviando e recebendo mensagens (a ponta
   fica ao alcance por ≈ 8 s a cada passagem).
4. **Afastamento:** envia `link_bye` e se afasta 40 m em linha reta pelo
   próprio eixo, com velocidade constante (5 m/s).
5. **Retorno:** volta pelo mesmo eixo ao ponto de acoplamento e espera de novo.

Os satélites são **só origem e destino**: trocam mensagens apenas com o hub e
apenas enquanto estão acoplados, recebem só as mensagens destinadas a eles e
não repassam nem guardam as de outros.

Como a formação gira em torno do próprio centro, **as duas pontas varrem o
perímetro** e passam por cada eixo uma vez por volta. Em 60 voltas houve **480
acoplamentos**: cada satélite acoplou 60 vezes no C5 e 60 vezes no C9,
alternando. As pontas estão separadas por ≈ 145° no giro, então as passagens
por um eixo se alternam a cada ≈ 24 s e ≈ 36 s.

### 2.4 Tráfego

- **Pares opostos:** S1 ↔ S3 (leste–oeste) e S2 ↔ S4 (norte–sul).
- **Uma mensagem por acoplamento**, criada na hora do contato para o satélite
  do eixo oposto.
- **60 voltas simuladas** (60 min). Na última volta não há mensagens novas, só
  entrega das pendentes: são **472 mensagens** no total (8 acoplamentos por
  volta, em 59 voltas).

---

## 3. Princípios de enxame

| Princípio | Como foi atendido |
|---|---|
| **Descentralização** (sem conhecimento ou ordens globais) | Nenhum nó consulta posição ou estado de outro nó, a não ser pelo que recebe por rádio dos vizinhos. |
| **Sensoriamento e comunicação local** | Beacons de enlace com alcance de 30 m; tabelas montadas só com o que é ouvido ou anunciado pelos vizinhos. |
| **Plano compartilhado** (Informações fornecidas previamente) | Topologia em V, padrão de rotação (centro e vel. angular ω) e eixo de cada nó satélite.|
| **Papel do Líder na formação** | C1 voa pelo plano; cada nó segue o seu pai na árvore. O líder não tem papel especial na transmissão de mensagens, apenas é o nó de referência a ser seguido. |
| **Escalabilidade e robustez** | Atualizações de alcance só por eventos (conexão e desconexão); entrega diferida quando o destino está fora. |

---

## 4. Camada comum (igual para todos os protocolos)

Implementada em `src/node.py`. **Não entra nas métricas de roteamento**, porque o
custo é o mesmo em todos os protocolos.

- **Beacons de enlace:** cada nó anuncia id, papel, posição e, no Core, o ângulo
  da formação, a cada 0,2 s. Um vizinho é considerado perdido após 1 s sem beacon.
- **Formação em cascata:** cada nó segue o pai com o deslocamento do V. O atraso
  do beacon é compensado pela **rotação rígida do plano**, e não pela velocidade
  medida. Extrapolar pela velocidade medida amplificava o erro ao longo da
  cascata, e a ponta C9 chegava a se soltar.
- **Handshake e ciclo dos satélites:** conforme a seção 2.3. O `seq` de cada
  handshake é ecoado no ACK e usado no `link_bye`, para descartar avisos velhos.
- **Satélites só no acoplamento:** um satélite cria a mensagem ao acoplar e a
  entrega ao hub; troca mensagens apenas com o hub e só recebe as destinadas a
  ele. O nó do Core só troca mensagens com um satélite acoplado a ele. A regra
  vale igual para os 4 protocolos.
- **Ritmo do modo 3D** (`src/pacing.py`): o visualizador acelera o tempo pelo
  fator `VIZ_SPEEDUP` (30×: os 60 min simulados passam em 2 min; medi ≈ 29,8×
  sem o browser aberto). O `real_time` do GrADySim espera antes de cada
  evento e acumula atraso (pedindo 30×, medi só ≈ 5×); por isso criei um
  controle de ritmo com prazos absolutos, que segue o fator pedido.

---

## 5. Protocolos

Os três protocolos de referência seguem os slides da disciplina e as
referências da seção 12.

### 5.1 Flooding (`src/routing/flooding_mixin.py`)

- Cada nó retransmite cada mensagem **uma vez** (supressão de duplicatas).
- TTL = 10, o diâmetro da rede (satélite → ponta → … → outra ponta →
  satélite), decrementado a cada salto.
- **Self-pruning** (Lim & Kim): quem transmite anexa a sua lista de vizinhos;
  o receptor só retransmite se tiver algum vizinho fora dessa lista. É o
  "escolher **alguns** ou todos os vizinhos" do slide.
- **ACK do receptor:** na primeira entrega, o destino inunda uma confirmação de
  volta à origem (controle), com as mesmas regras. Só confirma; não há
  retransmissão.
- Os nós intermediários não guardam nada. Se não houver caminho até o destino
  no instante da inundação, a mensagem se perde.

### 5.2 GeoCast (`src/routing/geocast_mixin.py`)

Encaminha "na direção" do destino, como no slide e em Choi et al.:

1. Se o nó ouve o destino, entrega direto.
2. Se está dentro da **zona-alvo** (esfera de 10 m em volta da posição
   prevista do destino), **inunda localmente**; só nós dentro da zona
   retransmitem.
3. Senão, **guloso**: unicast ao vizinho mais perto do destino, desde que mais
   perto que o próprio nó. A posição dos vizinhos vem dos beacons; as
   distâncias são em 3D.
4. Se nenhum vizinho avança (**mínimo local**, ou vazio de cobertura), faz a
   **busca de rota** de Choi et al. (seção II.B), que corresponde ao "contornar
   áreas sem cobertura (se possível)" do slide:
   - difunde uma busca (controle) que se propaga salto a salto só por nós da
     região na direção do destino: a até a distância do nó preso + 80 m (4L),
     com até 10 saltos;
   - o primeiro nó mais perto do destino que o nó preso responde pelo caminho
     inverso;
   - os dados seguem esse caminho, e a partir de quem respondeu o guloso
     recomeça.
5. Sem resposta em 0,5 s, descarta ("sem rota"). Não há armazenamento nos
   intermediários.

A posição do destino vem do **plano**: o ponto de acoplamento do satélite, no
seu eixo. Como cada mensagem vai para o satélite oposto, que nesse momento está
parado no seu ponto, a previsão coincide com a posição real: neste cenário o
GeoCast falha por falta de caminho, não por erro de posição.

### 5.3 DTN (`src/routing/dtn_mixin.py`)

Store-carry-forward com **troca completa no encontro**, como no slide: entrega
eventual pelos nós em movimento, trocando **todas** as mensagens que faltam a
cada encontro ("swap all messages"). Arsheen et al. motivam o uso de DTN em
FANETs esparsas, com topologia que muda com frequência.

- Cada nó guarda cópias no buffer, **sem limite nem prazo** (armazenamento
  ilimitado no Core).
- **Vetor-resumo** (controle): os ids que o nó tem e os ids que sabe já terem
  sido entregues ("aviso de entrega"). É enviado:
  - ao ganhar um vizinho novo (encontro);
  - quando o buffer ganha mensagens novas. Os nós do Core estão sempre em
    contato entre si e nunca geram "encontro novo"; sem esse gatilho, a
    mensagem travaria no primeiro salto.
- Quem recebe o resumo envia, num lote, as mensagens que o outro não tem.
- O aviso de entrega apaga as cópias de mensagens já entregues.
- Usa só informação local: nenhuma posição e nenhuma lista global de nós.

### 5.4 SwCore (`src/routing/swcore_mixin.py`)

Cada nó do Core conhece apenas os seus vizinhos na árvore e mantém uma **tabela
por destino** (cada satélite), com o `seq` do handshake:

| Estado | Significado |
|---|---|
| **AbleToDeliverDirectly** | O satélite fez handshake comigo (sou o hub): entrego direto |
| **NextHop(Uy)** | Repasso pelo vizinho Uy da árvore |
| **Unreachable** | Ninguém o alcança agora: guardo a mensagem |

- **Conexão:** o hub marca AbleToDeliverDirectly e envia `REACH(ep, seq)` pela árvore. Cada
  receptor faz `tabela[ep] = remetente` e repassa aos outros vizinhos da árvore.
  Não há laços, porque a topologia é uma árvore.
- **Desconexão:** o hub envia `UNREACH(ep, seq)`. Anúncios com `seq` menor que o
  da tabela são descartados.
- **Encaminhamento, nesta ordem:**
  1. AbleToDeliverDirectly → entrega ao satélite;
  2. NextHop → repassa;
  3. Unreachable → **guarda**, sem prazo (armazenamento ilimitado), até
     chegar um REACH do destino.
- Cada anúncio custa **8 transmissões** (uma por aresta da árvore) e só ocorre
  quando algo muda.

**Exemplo real** (`logs/swcore.log`):

| t | Evento |
|---|---|
| 11,2 s | S4 acopla no C9, cria `S4>S2#1` e entrega ao hub; S2 está inalcançável, então o C9 guarda |
| 17,1 s | S2 acopla na outra ponta (C5); o REACH chega ao C9, e a mensagem atravessa a árvore: C9 → C8 → C7 → C6 → C1 → C2 → C3 → C4 → C5 → S2 |
| | Entregue com **10 saltos e 5,96 s** |

---

## 6. Métricas

Definidas em `src/metrics.py`; a legenda completa está em `results.md`.

- **PDR:** entregues / criadas (eficácia).
- **Latência** média, mediana e máxima; **saltos médios**.
- **Tx dados:** pacotes de dados. **Msgs dados tx:** mensagens transmitidas,
  contando cada uma dentro dos lotes do DTN, para comparar a carga útil.
- **Tx controle:** anúncios do SwCore, vetores-resumo do DTN, ACKs do
  receptor no Flooding e buscas e respostas de rota do GeoCast.
- **Podas:** retransmissões evitadas (self-pruning no Flooding; nó fora da
  zona-alvo no GeoCast). **Contornos:** vazios contornados pela busca de rota
  do GeoCast. **Sem rota:** descartes do GeoCast num vazio que a busca não
  contornou. **ACKs origem:** confirmações que voltaram à origem no Flooding.
- **Tx / entrega:** custo em transmissões por entrega (eficiência).
- **Energia:** 1 por transmissão + 0,5 por recepção (unidades arbitrárias).

---

## 7. Resultados

Gerados por `python main.py 5` (60 voltas, 472 mensagens); reproduzidos de
`results.md`.

| Protocolo | PDR | Lat. média | Lat. mediana | Saltos | Tx dados | Msgs dados tx | Tx controle | Tx / entrega | Rx redund. | Energia | Energia / entrega |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Flooding | 0% | n/d | n/d | n/d | 4248 | 4248 | 0 | n/d | 3304 | 8732 | n/d |
| GeoCast | 0% | n/d | n/d | n/d | 3776 | 3776 | 3304 | n/d | 0 | 12036 | n/d |
| DTN | **100%** | 18,0 s | 17,9 s | 6,00 | 4485 | 4720 | 12514 | 36,0 | 0 | 29280 | 62,0 |
| **SwCore** | **100%** | 18,0 s | 18,0 s | 6,00 | 2832 | 2832 | 7680 | **22,3** | 0 | **15768** | **33,4** |

Tx / entrega = (Tx dados + Tx controle) / entregues. No DTN, os 4485 pacotes de
dados são lotes com 4720 mensagens no total.

**Latência por caminho** (SwCore e DTN, iguais):

| Caminho | Mensagens | Latência | Saltos |
|---|---|---|---|
| A outra ponta chega primeiro ao satélite oposto: atravessa a árvore | 236 | ≈ 6 s | 10 |
| A mesma ponta chega primeiro, meia volta depois | 236 | ≈ 30 s | 2 |

Extras:
- o Flooding fez 472 podas (self-pruning) e nenhum ACK voltou, porque nenhuma
  mensagem chegou ao destino;
- o GeoCast fez 472 buscas de rota, todas sem resposta (472 descartes sem rota).

---

## 8. Discussão

- **A hipótese se confirma em parte.** O SwCore entrega 100%, tanto quanto o
  DTN, e é o mais **eficiente**:
  - **≈ 1,6× menos transmissões por entrega** que o DTN (22,3 contra 36,0);
  - **≈ 1,9× menos energia** que o DTN (15768 contra 29280) e a **menor energia
    por entrega** (33,4 contra 62,0);
  - **mas não tem menor latência:** os dois entregam cada mensagem no mesmo
    instante, quando a primeira ponta chega ao satélite oposto. Nenhum
    protocolo consegue adiantar isso; a latência é dada pela geometria.
- **As duas pontas são as extremidades.** Como o V gira em torno do próprio
  centro, C5 e C9 varrem o perímetro e os satélites acoplam nas duas. As
  pontas estão separadas por ≈ 145° no giro, o que cria dois caminhos:
  - **metade das mensagens** sai por uma ponta, e a outra ponta chega ao
    satélite oposto ≈ 35° depois (≈ 6 s): a mensagem **atravessa a árvore
    de uma ponta à outra** (10 saltos). É o "Core repassa até o lado oposto"
    do SwCore;
  - **a outra metade** sai por uma ponta que é ela mesma a primeira a chegar
    ao satélite oposto, meia volta depois (≈ 30 s, 2 saltos).
- **O custo do DTN é a replicação:** cada mensagem é transmitida 10 vezes
  (4720 contra 2832 do SwCore), porque é copiada para os 9 nós do Core, e o DTN
  troca 12514 vetores-resumo. O SwCore guarda uma única cópia e só a move pela
  árvore quando o destino aparece; o seu controle só ocorre em eventos: 960
  anúncios (480 conexões e 480 desconexões) × 8 arestas = 7680 transmissões.
- **Flooding e GeoCast não atravessam partições:** entregam 0 das 472
  mensagens. O par de satélites nunca está conectado ao mesmo tempo, e sem
  armazenamento no caminho a mensagem não espera o destino. É o "Network
  partitions are never bridged" do slide.
- **Flooding:** cada inundação percorre o V inteiro (9 transmissões por
  mensagem; 3304 recepções redundantes) e morre na ponta oposta. O
  self-pruning poda a retransmissão inútil dessa ponta, que só tem um
  vizinho (472 podas, uma por mensagem).
- **GeoCast:** o guloso leva a mensagem pelo V até o nó mais perto do ponto
  do satélite oposto (C8 ou C4, conforme a ponta de saída). Dali nenhum
  vizinho chega mais perto e o destino está fora do alcance: a busca de rota
  não acha ninguém, e as 472 mensagens são descartadas. É o "e se a zona de
  encaminhamento for esparsa e não houver rota completa?" do slide.
- **Geometria contra topologia:** o GeoCast decide pela distância geométrica
  e leva a mensagem para onde o destino está agora, que é vazio. O SwCore não
  precisa saber onde o destino está: guarda a mensagem no hub e, quando o
  destino acopla em qualquer ponta, o anúncio de alcance indica o caminho
  pela árvore.

---

## 9. Decisões de projeto e premissas

- **Giro em torno do próprio centro:** a formação gira em torno do seu
  centroide, como a formação circular da convenção. Assim as duas pontas
  ficam à mesma distância do centro (68,6 m) e são as extremidades onde os
  satélites acoplam, e a mensagem pode atravessar a árvore de um lado ao
  outro.
- **Abertura de 55°:** com L = 20 m e alcance de 30 m, nós de asas opostas
  ficariam ao alcance se cada asa abrisse menos de ≈ 48,6°. Escolhi 55° para
  ter folga (32,8 m).
- **Satélites:** descobrem os nós do Core pelo rádio (30 m) e acoplam no que
  passa pelo ponto de acoplamento (a até 10 m, uma das pontas); ficam 2 s
  trocando mensagens e se afastam 40 m pelo eixo a 5 m/s (ida e volta em
  16 s, antes da próxima ponta). Entre dois acoplamentos há pelo menos 15 s,
  mais que a janela de contato de uma ponta (≈ 8 s), para não acoplar duas
  vezes na mesma passagem.
- **Acoplamento sem disputa de ordem:** o hub manda a confirmação e, logo
  depois, as mensagens guardadas; os dois pacotes podem chegar ao satélite no
  mesmo instante, em qualquer ordem. Por isso o satélite aceita os pacotes do
  nó a quem pediu o acoplamento, mesmo antes da confirmação (sem isso, uma
  mensagem se perdia).
- **Tráfego:** uma mensagem por acoplamento, em pares opostos, para que cada
  mensagem tenha de atravessar a formação.
- **Satélites só origem e destino:** trocam mensagens só com o hub, durante o
  acoplamento, e recebem só as destinadas a eles (seção 2.3). Por isso o
  SwCore entrega sempre pelo estado AbleToDeliverDirectly, no hub.
- **Formação sem o plugin do GrADySim:** `MobilityLeader/FollowerPlugin` usa
  deslocamentos em eixos fixos (não giram com o V) e segue o primeiro líder que
  ouvir, o que é ambíguo numa cascata. Por isso, a formação usa os próprios
  beacons de enlace.
- **Alinhamento com os slides:** Flooding, GeoCast e DTN seguem o material da
  disciplina e as referências: self-pruning e ACK no Flooding, guloso com
  zona-alvo e contorno de vazios no GeoCast, troca completa no encontro no DTN.
- **Contorno de vazios no GeoCast:** segue a seção II.B de Choi et al. A
  previsão de posição dos vizinhos pela velocidade (Eq. 1 de Choi et al.) não
  foi implementada: os beacons levam só a posição. Com beacons a cada 0,2 s
  e as pontas a ≈ 7,2 m/s, a posição anunciada fica no máximo ≈ 1,4 m
  defasada, bem menos que o alcance de 30 m.

---

## 10. Como reproduzir

```bash
python main.py              # menu interativo
python main.py 5            # benchmark dos 4 protocolos (gera results.md e logs/)
python main.py 4 1          # SwCore no visualizador 3D (30× mais rápido: 60 min em 2 min)
python main.py 3 2          # DTN em modo rápido (sem browser)
```

- Logs de eventos: `logs/<protocolo>.log`.
- Parâmetros: todos em `src/config.py`.

## 11. Estrutura do código

| Arquivo | Conteúdo |
|---|---|
| `main.py` | Menu e atalhos de linha de comando |
| `src/config.py` | Todos os parâmetros |
| `src/scenario.py` | Plano compartilhado: geometria, árvore, eixos e pontos de acoplamento |
| `src/node.py`, `src/nodes.py` | Camada comum (enlace, formação em cascata, handshake e ciclo dos satélites) e a montagem do nó de cada protocolo |
| `src/pacing.py` | Ritmo acelerado do modo 3D |
| `src/routing/` | `base` + um mixin por protocolo + `messages` |
| `src/metrics.py`, `src/motor.py` | Métricas, execução e tabela |
| `src/viz.py`, `src/eventlog.py` | Visualização 3D e log em arquivo |

## 12. Referências

- **DTN:** S. Arsheen, A. Wahid, K. Ahmad, K. Khalim, "Flying Ad hoc Network
  Expedited by DTN Scenario: Reliable and Cost-effective MAC Protocols
  Perspective," *2020 IEEE 14th International Conference on Application of
  Information and Communication Technologies (AICT)*, Tashkent, 2020, pp. 1–6,
  doi: 10.1109/AICT50176.2020.9368575.
- **Flooding:** H. Lim, C. Kim, "Flooding in wireless ad hoc networks,"
  *Computer Communications*, vol. 24, nº 3–4, pp. 353–363, 2001,
  doi: 10.1016/S0140-3664(00)00233-4.
- **GeoCast:** S.-C. Choi, H. R. Hussen, J.-H. Park, J. Kim, "Geolocation-Based
  Routing Protocol for Flying Ad Hoc Networks (FANETs)," *2018 Tenth
  International Conference on Ubiquitous and Future Networks (ICUFN)*, Prague,
  2018, pp. 50–52, doi: 10.1109/ICUFN.2018.8436724.
