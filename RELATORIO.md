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

Um único cenário para todos os protocolos: **mesma mobilidade e mesmo tráfego**,
com sementes fixas. Só o protocolo de roteamento muda.

### 2.1 Nós

| IDs | Papel | Descrição |
|---|---|---|
| 0 | Base Station (BS) | Estação base fixa no centro (z = 2 m) |
| 1–9 | Core | Formação em V: C1 no ápice, C2–C5 na asa externa, C6–C9 na asa interna (z = 10 m) |
| 10–13 | Satélites | S1–S4, um por setor (0°, 90°, 180°, 270°), z = 12 m |

### 2.2 Geometria do Core

| Parâmetro | Valor | Motivo |
|---|---|---|
| Distância entre vizinhos diretos (L) | 5 m | Enunciado |
| Alcance do rádio (D = L + ε) | 6 m (ε = 1 m) | Alcança **só** os vizinhos diretos |
| Abertura de cada asa | 45° | Com menos de ≈37°, nós de asas opostas ficariam ao alcance um do outro |
| Raio do ápice (R) | 25 m | Ponta externa a 41,6 m do centro; ponta interna a 17,8 m |
| Período de rotação | 120 s | "O Core gira devagar em torno de um ponto central" |
| Árvore geradora | As 8 arestas do V | C1–C2–C3–C4–C5 e C1–C6–C7–C8–C9 |

**Rigidez medida** (SwCore, 400 s): arestas da árvore entre **4,93 e 5,08 m**;
pares não vizinhos sempre a **≥ 7,06 m**, fora do alcance de 6 m.

### 2.3 Satélites

Cada satélite trabalha no seu setor, numa órbita (*shell*) com o raio do seu
lado do V:

| Satélite | Setor | Lado (shell) |
|---|---|---|
| S1 | 0° | Ponta externa (C5), r = 41,6 m |
| S2 | 90° | Ponta externa (C5), r = 41,6 m |
| S3 | 180° | Ápice (C1), r = 25 m |
| S4 | 270° | Ápice (C1), r = 25 m |

Ciclo de cada satélite:

1. **Patrulha:** voa livremente perto do setor (±12° e ±3 m) e acumula as
   mensagens que cria.
2. **Aproximação:** 10 s antes da passagem do seu lado, prevista pelo plano
   compartilhado, vai ao ponto de encontro.
3. **Handshake:** escolhe o **hub** entre os nós do Core que ouve (o seu lado,
   se ouvido; senão o mais próximo) e confirma com `link_req`/`link_ack`.
4. **Tandem:** voa 2 m acima do hub, acompanhando-o, por um tempo sorteado
   entre T e 4T (T = 5 s).
5. **Despedida:** envia `link_bye` e volta à patrulha.

Em 400 s há **14 tandems** (3 a 4 por satélite), um a cada ≈120 s por satélite.

### 2.4 Estação base

- Antena com alcance de **22 m**, implementada em `src/radio.py`. Alcança a asa
  interna (C7–C9), mas não o ápice nem os satélites.
- O GrADySim tem um único alcance para todos os nós. Por isso, todo enlace com a
  BS numa das pontas usa 22 m; o enlace é tratado como **simétrico**.
- A BS faz o mesmo handshake dos satélites. Como o centro de rotação coincide
  com a BS, a distância até a asa interna não muda e o hub dela fica fixo (C9).

### 2.5 Tráfego

O tráfego tem 165 mensagens entre t = 3 s e t = 240 s, com intervalo sorteado
de 4 a 10 s por origem (semente 42).

| Fluxo | Mensagens |
|---|---|
| Satélite → outro satélite | 91 |
| Satélite → BS | 40 |
| BS → satélite (comandos) | 34 |

A simulação vai até **t = 400 s**, de modo que toda mensagem tem pelo menos uma
volta completa do Core para ser entregue.

---

## 3. Princípios de enxame

| Princípio | Como foi atendido |
|---|---|
| **Descentralização** (sem conhecimento ou ordens globais) | Nenhum nó consulta posição ou estado de outro nó, a não ser pelo que recebe por rádio dos vizinhos. |
| **Sensoriamento e comunicação local** | Beacons de enlace com alcance de 6 m; tabelas montadas só com o que é ouvido ou anunciado pelos vizinhos. |
| **Plano compartilhado** (Informações fornecidas previamente) | Topologia em V, padrão de rotação (centro e vel. angular ω), setor de cada nó satélite e posição de BS.|
| **Papel do Líder na formação** | C1 voa pelo plano; cada nó segue o seu pai na árvore. O líder não tem papel especial na transmissão de mensagens, apenas é o nó de referência a ser seguido. |
| **Escalabilidade e robustez** | Atualizações de alcance só por eventos (conexão e desconexão); entrega diferida quando o destino está fora; nós vizinhos servem de *backup*. |

---

## 4. Camada comum (igual para todos os protocolos)

Implementada em `src/node.py`. **Não entra nas métricas de roteamento**, porque o
custo é o mesmo em todos os protocolos.

- **Beacons de enlace:** cada nó anuncia id, papel, posição e, no Core, o ângulo
  da formação. Intervalos: Core 0,2 s, satélites 0,5 s, BS 1 s. Um vizinho é
  considerado perdido após 1,5 s sem beacon.
- **Formação em cascata:** cada nó segue o pai com o deslocamento do V. O atraso
  do beacon é compensado pela **rotação rígida do plano**, e não pela velocidade
  medida. Extrapolar pela velocidade medida amplificava o erro ao longo da
  cascata, e a ponta C9 chegava a se soltar.
- **Handshake e tandem:** conforme a seção 2.3. O `seq` de cada handshake é
  ecoado no ACK e usado no `link_bye`, para descartar avisos velhos.
- **Fila na origem:** um endpoint acumula as mensagens que cria enquanto está
  isolado e as libera ao ganhar contato. Sem isso, Flooding e GeoCast
  entregariam quase 0%, porque o satélite quase sempre transmite sem ninguém ao
  alcance.

---

## 5. Protocolos

Os três protocolos de referência seguem os slides da disciplina e as
referências da seção 13.

### 5.1 Flooding (`src/routing/flooding_mixin.py`)

- Cada nó retransmite cada mensagem **uma vez** (supressão de duplicatas).
- TTL = 10, o diâmetro da rede (satélite → ponta → … → outra ponta → BS),
  decrementado a cada salto.
- **Self-pruning** (Lim & Kim): quem transmite anexa a sua lista de vizinhos;
  o receptor só retransmite se tiver algum vizinho fora dessa lista. É o
  "escolher **alguns** ou todos os vizinhos" do slide.
- **ACK do receptor:** na primeira entrega, o destino inunda uma confirmação de
  volta à origem (controle), com as mesmas regras. Só confirma; não há
  retransmissão.
- Armazena só na origem; os nós intermediários não guardam nada. Se não houver
  caminho até o destino no instante da inundação, a mensagem se perde.

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
     região na direção do destino: a até a distância do nó preso + 20 m, com
     até 10 saltos;
   - o primeiro nó mais perto do destino que o nó preso responde pelo caminho
     inverso;
   - os dados seguem esse caminho, e a partir de quem respondeu o guloso
     recomeça.
5. Sem resposta em 0,5 s, descarta ("sem rota"). Não há armazenamento nos
   intermediários.

A posição do destino vem do **plano**: o ponto do setor do satélite ou o
centro, para a BS. Ela erra quando o satélite está em tandem, longe do setor.
É a fraqueza esperada do GeoCast com mobilidade.

### 5.3 DTN (`src/routing/dtn_mixin.py`)

Store-carry-forward com **troca completa no encontro**, como no slide: entrega eventual pelos nós em
movimento, trocando **todas** as mensagens que faltam a cada encontro ("swap
all messages"). Arsheen et al. motivam o uso de DTN em FANETs esparsas, com
topologia que muda com frequência.

- Cada nó guarda cópias no buffer; cada cópia expira 250 s após a criação.
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
por endpoint** (satélite ou BS), com o `seq` do handshake:

| Estado | Significado |
|---|---|
| **Direct** | O endpoint fez handshake comigo (sou o hub) |
| **NextHop(Uy)** | Repasso pelo vizinho Uy da árvore |
| **Unreachable** | Ninguém o alcança agora: guardo a mensagem |

- **Conexão:** o hub marca Direct e envia `REACH(ep, seq)` pela árvore. Cada
  receptor faz `tabela[ep] = remetente` e repassa aos outros vizinhos da árvore.
  Não há laços, porque a topologia é uma árvore.
- **Desconexão:** o hub envia `UNREACH(ep, seq)`. Anúncios com `seq` menor que o
  da tabela são descartados.
- **Encaminhamento, nesta ordem:**
  1. Direct → entrega ao endpoint;
  2. NextHop → repassa;
  3. Unreachable, mas o nó ouve o endpoint → entrega direto (*backup*);
  4. Unreachable → **guarda** (entrega diferida, até 150 s) até chegar um REACH.
- Cada anúncio custa **8 transmissões** (uma por aresta da árvore) e só ocorre
  quando algo muda.

**Exemplo real** (`logs/swcore.log`):

| t | Evento |
|---|---|
| 26,3 s | S3 cria `S3>S1#3` e a acumula, pois está isolado |
| 56,0 s | S3 entra em tandem e entrega ao hub C1; S1 está inalcançável, então C1 guarda |
| 124,5 s | S1 conecta ao C5, o REACH chega ao C1, e a mensagem segue C1→C2→C3→C4→C5→S1 |
| | Entregue com **6 saltos e 98,2 s** |

---

## 6. Métricas

Definidas em `src/metrics.py`; a legenda completa está em `results.md`.

- **PDR:** entregues / criadas (eficácia).
- **Latência** média e mediana; **saltos médios**.
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

### 7.1 Tabela geral

Gerada por `python main.py 5`; reproduzida de `results.md`.

| Protocolo | PDR | Lat. média | Saltos | Tx dados | Msgs dados tx | Tx controle | Tx / entrega | Rx redund. | Entregas dupl. | Energia | Energia / entrega |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Flooding | 26,7% | 39,4 s | 5,43 | 1365 | 1365 | 313 | 38,1 | 1553 | 42 | 3664 | 83,3 |
| GeoCast | 26,7% | 39,4 s | 5,48 | 778 | 778 | 1320 | 47,7 | 8 | 0 | 3964 | 90,1 |
| DTN | **100%** | **77,9 s** | 4,68 | 663 | 1967 | 1536 | 13,3 | 100 | 0 | 3748 | 22,7 |
| **SwCore** | **100%** | 81,5 s | 6,22 | 1026 | 1026 | 224 | **7,6** | 0 | 0 | 1875 | **11,4** |

Tx / entrega = (Tx dados + Tx controle) / entregues. No DTN, os 663 pacotes de
dados são lotes com 1967 mensagens no total.

Extras:
- o Flooding fez 499 podas (self-pruning) e recebeu os 44 ACKs;
- o GeoCast fez 158 buscas de rota: 42 contornaram o vazio e 116 não acharam
  rota.

### 7.2 Entrega por tipo de fluxo

| Protocolo | Sat → Sat (91) | Sat → BS (40) | BS → Sat (34) |
|---|---|---|---|
| Flooding | 0 | 39 (44,4 s) | 5 (0,1 s) |
| GeoCast | 0 | 39 (44,4 s) | 5 (0,1 s) |
| DTN | 91 (101,1 s) | 40 (46,0 s) | 34 (53,1 s) |
| SwCore | 91 (104,1 s) | 40 (51,3 s) | 34 (56,7 s) |

Cada célula mostra as mensagens entregues e, entre parênteses, a latência média.

---

## 8. Discussão

- **A hipótese se confirma em parte.** O SwCore entrega 100%, tanto quanto o
  DTN, e é o mais **eficiente**:
  - **≈ 1,8× menos transmissões por entrega** que o DTN (7,6 contra 13,3);
  - **≈ 2× menos energia** que o DTN (1875 contra 3748) e a **menor energia por
    entrega** de todos (11,4);
  - **mas não tem a menor latência:** o DTN é ≈ 4% mais rápido
    (77,9 s contra 81,5 s), e mais rápido nos três tipos de fluxo. Com cópias
    espalhadas por todo o Core, quem estiver perto do destino quando ele
    reconecta já tem a mensagem. No SwCore, a mensagem retida ainda precisa
    percorrer a árvore até o hub.
- **O custo do DTN é a replicação:** 1967 mensagens transmitidas (contra
  1026 do SwCore), 1536 vetores-resumo e 100 recepções redundantes. O SwCore,
  com cópia única pela árvore, não gera nenhuma redundância, e o seu controle só ocorre em eventos: 28 anúncios (15 conexões,
  incluindo a da BS, e 13 desconexões) × 8 arestas = 224 transmissões.
- **Mais saltos não significam ineficiência:** o SwCore tem mais saltos médios
  (6,22) que o DTN (4,68) porque segue a árvore. Mesmo assim, o seu custo
  total é o menor.
- **Flooding e GeoCast não atravessam partições:** entregam 0 das 91 mensagens
  entre satélites. Os tandems dos satélites nunca acontecem ao mesmo tempo, e
  sem armazenamento no caminho a mensagem não espera o destino. Quase tudo o
  que entregam é satélite → BS, porque a BS está sempre conectada.
- **A latência baixa do Flooding é ilusória** (viés de sobrevivência): ele só
  entrega as mensagens fáceis, com o destino já conectado, e perde as difíceis.
- **Self-pruning e ACK no Flooding:** o self-pruning evitou 499
  retransmissões e reduziu as transmissões de dados em ≈ 21% (1365 contra
  1737 sem poda) sem perder nenhuma entrega; as entregas duplicadas caíram de
  84 para 42. Os 44 ACKs voltaram à origem: a ida e volta leva ≈ 0,1 s, e a
  topologia não muda nesse intervalo, como supõe o slide. Um detalhe de
  implementação: quem acabou de enviar um pacote ao nó também conta como
  vizinho na poda. Um satélite pode transmitir antes de o seu primeiro beacon
  chegar, e sem essa regra um ACK era podado por engano.
- **GeoCast:** ilustra as duas condições do slide, posição precisa e
  mobilidade limitada. Medi o protocolo **sem** e **com** o contorno de
  vazios de Choi et al.:

  | GeoCast | Entregues | Tx dados | Tx controle | Energia | Energia / entrega |
  |---|---|---|---|---|---|
  | Só guloso (sem contorno) | 40 (24,2%) | 607 | 0 | 914 | 22,9 |
  | Com contorno (versão final) | 44 (26,7%) | 778 | 1320 | 3964 | 90,1 |

  - **Sem contorno**, é o mais barato de todos e tem só 8 recepções
    redundantes, como prevê o slide ("muito menos retransmissões que o
    Flooding"). Mas 120 mensagens morrem em vazios: na ponta do V, no ápice ou
    na própria BS, que no centro fica mais perto de um setor oposto do que
    qualquer nó da asa interna.
  - **Com contorno**, houve 158 buscas de rota: 120 mensagens travaram uma
    vez, e 38 delas travaram de novo depois do contorno. 42 buscas acharam
    caminho, e só **4 dessas mensagens foram entregues** (comandos BS →
    satélite). As outras 38, todas entre satélites, morreram mais adiante,
    porque o destino estava isolado e não havia caminho nenhum até ele.
  - **"Falso contorno" pela BS:** em 30 dos 42 contornos, quem respondeu à
    busca foi a BS. Ela está mais perto do destino que o nó preso, que é a
    regra de Choi et al. para responder, mas no centro ela também é um mínimo
    local: os seus vizinhos (C7–C9) estão todos mais longe. A mensagem trava
    de novo na BS logo em seguida. É um efeito da geometria do cenário (V
    girando em torno da BS), não um defeito da regra.
  - **Geometria contra topologia:** o GeoCast decide pela distância
    geométrica, e a BS, no centro, está geometricamente perto do destino,
    mas é topologicamente um beco sem saída. O SwCore conhece a topologia da
    árvore e, sem rota, guarda a mensagem em vez de inundar buscas inúteis.
  - **Contornar só ajuda se existe caminho.** O ganho foi de 4 entregas,
    igualando o Flooding (44), a um custo ≈ 4× maior em energia: as buscas
    inundam a região a cada mínimo local. É o "e se a zona de encaminhamento
    for esparsa e não houver rota completa?" do slide.
  - **Posição prevista:** 3 comandos para S3/S4 ainda entram cedo demais na
    zona-alvo pela ponta C9, que chega a ≈ 7,4 m da posição prevista (dentro
    da esfera de 10 m, mas fora do alcance de rádio). A inundação local então
    morre na asa interna.

---

## 9. Decisões de projeto e premissas

- **Raios das órbitas:** S1 e S2 na ponta externa, S3 e S4 no ápice. Assim, os
  pares opostos (0°↔180° e 90°↔270°) estão em lados diferentes do V, e o Core
  repassa as mensagens internamente de um lado ao outro, como pede o enunciado.
- **A BS cobre a asa interna:** a terceira "ponta" do V fica para a BS, e cada
  extremidade atende um grupo de endpoints.
- **Formação sem o plugin do GrADySim:** `MobilityLeader/FollowerPlugin` usa
  deslocamentos em eixos fixos (não giram com o V) e segue o primeiro líder que
  ouvir, o que é ambíguo numa cascata. Por isso, a formação usa os próprios
  beacons de enlace.
- **Fila na origem para todos os protocolos:** ver a seção 4.
- **Alinhamento com os slides:** Flooding, GeoCast e DTN foram revisados para
  seguir o material da disciplina e as referências: self-pruning e ACK no
  Flooding, guloso com zona-alvo no GeoCast, troca completa no encontro no DTN. A versão
  anterior do DTN (idade de encontro, estilo FRESH/PRoPHET) foi removida por
  não constar no slide nem na referência.
- **Contorno de vazios no GeoCast:** acrescentado depois de ler Choi et al.,
  para seguir a referência e o slide. A previsão de posição dos vizinhos pela
  velocidade (Eq. 1 de Choi et al.) não foi implementada: os beacons levam só
  a posição, e o Core se move devagar (≈ 0,9 a 2,2 m/s, da ponta interna à externa).


## 10. Como reproduzir

```bash
python main.py              # menu interativo
python main.py 5            # benchmark dos 4 protocolos (gera results.md e logs/)
python main.py 4 1          # SwCore no visualizador 3D
python main.py 3 2          # DTN em modo rápido (sem browser)
```

- Logs de eventos: `logs/<protocolo>.log`.
- Parâmetros: todos em `src/config.py`.

## 11. Estrutura do código

| Arquivo | Conteúdo |
|---|---|
| `main.py` | Menu e atalhos de linha de comando |
| `src/config.py` | Todos os parâmetros |
| `src/scenario.py` | Plano compartilhado: geometria, árvore, setores, tráfego |
| `src/node.py` | Camada comum: enlace, formação em cascata, handshake e tandem |
| `src/radio.py` | Alcance maior da BS |
| `src/routing/` | `base` + um mixin por protocolo + `messages` |
| `src/metrics.py`, `src/motor.py` | Métricas, execução e tabela |
| `src/viz.py`, `src/eventlog.py` | Visualização 3D e log em arquivo |

## 13. Referências

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
