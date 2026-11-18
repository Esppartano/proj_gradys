# Relatório — T2: Pub/Sub distribuído sobre o SwCore

**Disciplina:** INF2541 · **Simulador:** GrADySim 0.8.0

---

## 1. Objetivo

Construir um serviço **Publish/Subscribe distribuído** sobre o roteamento
SwCore do T1, no mesmo enxame em V:

- satélites e nós do Core **assinam** tópicos e **publicam** neles, sem que o
  autor saiba quem vai receber;
- cada assinatura tem um **filtro pela região de origem** da publicação:
  N, E, S, W (os eixos dos satélites) ou C (o Core). Exemplos: {N, S, E},
  {N, S}, {E, W}, {C, S};
- as notificações chegam a todos os assinantes cujo filtro aceita a
  publicação, **pelo SwCore**;
- o serviço tem de funcionar com a **falha de core** da disciplina: a cada
  30 s, um nó do Core sorteado fica incomunicável por 1 s.

---

## 2. Cenário

A geometria, o ciclo dos satélites e a camada comum são os do T1
([RELATORIO.md](RELATORIO.md), seções 2 a 4): Core em V com 9 nós a 20 m,
uma volta por minuto em torno do próprio centro, rádio de 30 m, 4 satélites
nos eixos E, N, W, S que acoplam na ponta do V que passa. Também são 60 min
simulados, e a última volta só escoa o que está pendente.

Duas regras da disciplina entram neste trabalho:

| Regra | Implementação |
|---|---|
| A tabela de rotas (RT) de cada nó do Core inclui os outros 8 nós do Core, não só os satélites | Seção 4.1 |
| A cada 30 s, um nó do Core aleatório fica incomunicável (vizinhos do Core e satélites) por 1 s | Seção 4.2 |

---

## 3. Princípios de enxame

| Princípio | Como foi atendido |
|---|---|
| **Descentralização** | Não há servidor central: o estado do Pub/Sub fica replicado em 3 PSPeers, e qualquer um deles atende um pedido. Cada nó só sabe o que recebe dos vizinhos. |
| **Comunicação local** | Todo tráfego do Pub/Sub vai salto a salto pelo SwCore, com o rádio de 30 m. Não há rádio de longo alcance. |
| **Plano compartilhado** | Além do plano do T1 (V, rotação, eixos), todos conhecem a árvore e quais nós são PSPeers. Com isso, cada nó do Core sabe qual PSPeer está mais perto dele. |
| **Robustez** | Confirmação a cada salto, retransmissão, ressincronização da tabela ao reencontrar um vizinho e armazenamento ilimitado no Core. A falha de um nó não perde nenhuma mensagem (seção 8). |
| **A falha simula o canal, não o protocolo** | Nenhum nó sabe quando outro vai falhar: o nó em falha só fica sem rádio, e os outros só percebem que deixaram de ouvi-lo. |

---

## 4. SwCore usado no T2 (`src/routing/swcore_mixin.py`)

### 4.1 Tabela com os 8 nós do Core

Cada nó do Core mantém uma entrada para cada satélite e para cada um dos
outros 8 nós do Core. Ninguém recebe a tabela pronta: ela é aprendida por
anúncios.

- Ao ouvir um vizinho da árvore, o nó lhe envia um **SYNC**. O SYNC traz a
  entrada do próprio nó (`REACH` de si mesmo) e o resto da tabela, menos o que
  foi aprendido desse vizinho.
- Cada entrada é tratada como um anúncio e se espalha pela árvore. Até
  t = 0,16 s, todo nó sabe o próximo salto para os outros 8 (medido).

Exemplo: C1 vai por C2 até C2–C5 e por C6 até C6–C9; C5 vai sempre por C4.

### 4.2 Falha de core (`src/scenario.py`, `src/node.py`)

- Em t = 30, 60, 90, … s, um nó do Core é sorteado com semente fixa
  (`FAILURE_SEED`). Por isso, todas as execuções têm a mesma sequência de
  falhas.
- Durante 1 s, esse nó não transmite nem recebe nada. Todo envio de rádio
  passa por um único ponto (`_transmit`), e o que chega ao nó em falha é
  descartado.
- Pacote que não sai não conta nas métricas nem na energia.

### 4.3 Como o SwCore aguenta a falha

Uma falha de 1 s quase não é percebida pelo enlace, porque um vizinho só é
dado como perdido após 1 s sem beacon. Por isso, o SwCore tem três
mecanismos:

| Mecanismo | Funcionamento |
|---|---|
| **Confirmação a cada salto (HOP_ACK)** | Quem recebe um dado responde HOP_ACK a quem o enviou. Sem HOP_ACK em 0,2 s, o remetente tenta de novo: o Core reroteia ou guarda a mensagem, e o satélite a devolve à fila até o próximo acoplamento. |
| **Próximo salto fora de alcance** | Se o enlace já marcou o próximo salto como perdido, o dado é guardado e sai de novo quando o nó volta a ser ouvido. |
| **SYNC no reencontro** | Ao voltar a ouvir um vizinho da árvore, o nó lhe manda a tabela inteira. Anúncios de satélites que se perderam durante a falha são recuperados assim. |

- **Repetidas:** uma retransmissão cujo HOP_ACK se perdeu chega com o mesmo
  número de saltos e é descartada. Já uma mensagem que volta por um nó
  porque o destino acoplou do outro lado chega com mais saltos e segue
  normalmente. No destino, só a primeira cópia é entregue.
- **UNREACH repetido:** se a entrada já está inalcançável, um UNREACH repetido
  não é repassado, para não reinundar a árvore a cada SYNC.

---

## 5. Pub/Sub (`src/pubsub.py`)

### 5.1 Papéis

| Papel | Nós | Função |
|---|---|---|
| **Cliente** | Os 13 nós | Assina e publica. Região de origem: S1 = E, S2 = N, S3 = W, S4 = S, Core = C. |
| **PSPeer** | C1 (líder), C3 e C7 | Guarda uma réplica do estado (publicações e histórico de filtros de cada assinante), faz o casamento e envia as notificações. |

**Posição dos PSPeers:** o líder C1 e um nó a 2 saltos em cada asa. Assim,
todo nó do Core fica a no máximo 2 saltos de um PSPeer:

| Nó | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
|---|---|---|---|---|---|---|---|---|---|
| PSPeer mais próximo | C1 | C1 | C3 | C3 | C3 | C1 | C7 | C7 | C7 |

C2 está a 1 salto de C1 e de C3, e C6 a 1 salto de C1 e de C7. Nos empates,
vence o PSPeer de menor número, C1.

### 5.2 Mensagens

Todas são dados do SwCore, com HOP_ACK a cada salto; o conteúdo vai no
campo `ps`.

| Tipo | De → para | Conteúdo |
|---|---|---|
| `request` | Cliente → PSPeer mais próximo | Uma assinatura ou uma publicação |
| `sync` | PSPeer → os outros 2 PSPeers | A mesma mudança, para manter as réplicas iguais |
| `notify` | PSPeer → assinante | Uma publicação |

- **Pedido de satélite:** o satélite não sabe em que nó vai acoplar, então
  endereça "o PSPeer mais próximo". O primeiro nó do Core que recebe o pedido
  troca esse endereço pelo PSPeer mais próximo dele.
- **Notificação para satélite:** o SwCore a guarda no Core até o satélite
  acoplar, como no T1.

### 5.3 Casamento sem duplicatas e sem perdas

- **Dono:** cada publicação tem um **dono**, o PSPeer que a recebeu do
  cliente. Só o dono a notifica, e ele lembra a quem já mandou: não há
  notificação duplicada.
- **Quando o dono notifica:**
  1. ao receber a publicação: todos os assinantes que já conhece;
  2. ao saber de uma assinatura, pelo cliente ou por `sync`: as publicações
     dele que essa assinatura deveria ter recebido.
- **Pedidos simultâneos:** se uma assinatura chega ao PSPeer A e uma
  publicação ao PSPeer B ao mesmo tempo, nenhuma das duas se perde. O `sync`
  da assinatura chega a B, que é o dono da publicação, e B a notifica.

### 5.4 Regra de entrega

O assinante *s* recebe a publicação *p* se:

- *s* não é o autor de *p*; e
- o filtro de *s* para o tópico de *p*, **vigente no instante em que *p* foi
  criada**, contém a região de *p*.

Uma assinatura nova de um tópico substitui o filtro anterior daquele tópico
dali em diante. Publicações anteriores à assinatura não são entregues.

A mesma regra serve de gabarito global nas métricas (seção 6).

### 5.5 Carga de trabalho

| Parâmetro (`src/config.py`) | Valor |
|---|---|
| Tópicos | T1, T2 |
| Sorteio de cada nó | a cada 5 s (`PS_INTERVAL`) |
| Assinatura nova por sorteio | 5% (todos os nós): tópico e filtro não vazio sorteados |
| Publicação por sorteio | 20% (nós do Core) |
| Publicação dos satélites | uma a cada acoplamento |
| Semente | `PS_SEED = 2026` |

Em 60 min: **1721 publicações** (1249 do Core e 472 dos satélites) e **459
assinaturas**.

### 5.6 Exemplos reais (`logs/pubsub.log`)

**Publicação de satélite** (`p11_15`, de S3 = W, tópico T1):

| t | Evento |
|---|---|
| 296,2 s | S3 publica ao acoplar no C9; o pedido vai C9 → C8 → C7, o PSPeer mais próximo |
| 296,2 s | C7 (dono) casa com os assinantes: notifica C1, C3, C5 e C6, e guarda as notificações de S1, S2 e S4, que estão longe; manda `sync` a C1 e C3 |
| 296,3 s | C6, C1, C3 e C5 recebem em < 0,1 s (C5 está a 6 saltos do C7) |
| 302,1 s | S1 acopla no C5; o REACH chega ao C7, e a notificação atravessa a árvore inteira até S1 (latência 5,9 s) |
| 311,2 s | A notificação de S4 sai quando S4 acopla no C9 |
| 317,1 s | S2 acopla no C5 e recebe a sua (latência 20,9 s) |

**Falha do líder** (C1 em falha de 30,0 a 31,0 s):

| t | Evento |
|---|---|
| 30,6 s | C6 publica `p5_1` e envia ao PSPeer C1, que está em falha |
| 30,8 s | Sem HOP_ACK em 0,2 s: C6 retransmite |
| 31,0 s | Sem HOP_ACK de novo, e o enlace já marcou C1 como perdido: C6 guarda |
| 31,2 s | C6 volta a ouvir C1 e troca SYNC com ele; a publicação sai. C1, que assina T2 com filtro {C, E, N, S, W} desde 27,0 s, a recebe e a replica para C3 e C7 |

---

## 6. Métricas

As métricas pedidas nos slides são medidas em `src/pubsub.py`
(`PubSubMetrics`) e `src/metrics.py` (`recovery`). As definições abaixo são
as adotadas neste trabalho.

| Métrica | Definição |
|---|---|
| **MDR** | Entregas esperadas que chegaram / entregas esperadas. "Esperadas" são os pares (assinante, publicação) que a regra da seção 5.4 exige. |
| **Falso positivo** | Entrega que a regra não exigia |
| **Falso negativo** | Entrega esperada que não chegou até o fim da simulação |
| **Fora de ordem** | Entrega esperada que chegou depois de uma publicação mais nova do mesmo autor, para o mesmo assinante |
| **Latência fim a fim** | Da criação da publicação à entrega: média, p95 e p99 |
| **Saltos médios** | Transmissões do autor ao PSPeer dono mais as do dono ao assinante |
| **Convergência de assinatura** | Da criação da assinatura até os 3 PSPeers a conhecerem |
| **Vazão** | Entregas esperadas por minuto simulado |
| **Recuperação do roteamento** | Do fim da falha até o nó e todos os seus vizinhos da árvore trocarem SYNC, nos dois sentidos |
| **Recuperação dos dados** | Do fim da falha até o 1º dado confirmado (HOP_ACK) enviado pelo nó ou a ele. Depende de haver tráfego passando pelo nó. |
| **Energia por entrega** | (1 por transmissão + 0,5 por recepção) / entregas esperadas |

- **Só entregas esperadas:** latência, saltos, fora de ordem, vazão e energia
  por entrega não contam os falsos positivos.
- **119 falhas, não 120:** a falha que começaria exatamente no fim da
  simulação não é contada.

---

## 7. Resultados

Gerados por `python main.py 6 2` (60 min) e reproduzidos de
`results_pubsub.md`. A coluna "sem falha" usa `CORE_FAILURE = False`, com a
mesma carga.

| Métrica | Com falha | Sem falha |
|---|---|---|
| Publicações / assinaturas | 1721 / 459 | 1721 / 459 |
| Entregas esperadas | 11471 | 11471 |
| **MDR** | **100%** | **100%** |
| Falsos positivos | 89 | 89 |
| Falsos negativos | 0 | 0 |
| Duplicadas | 0 | 0 |
| Fora de ordem | 359 (3,13%) | 355 (3,10%) |
| Latência média / p95 / p99 | 4,40 / 23,87 / 32,14 s | 4,39 / 23,87 / 32,14 s |
| Saltos médios | 4,90 | 4,90 |
| Convergência de assinatura | 4,11 s | 4,11 s |
| Vazão | 191,2 entregas/min | 191,2 entregas/min |
| Falhas de core | 119 | 0 |
| Recuperação do roteamento (média / máx.) | 0,087 / 0,220 s | — |
| Recuperação dos dados (média / máx.) | 0,920 / 10,250 s | — |
| Retransmissões por salto | 407 | 0 |
| Tx dados / Tx controle | 55388 / 63166 | 54998 / 62750 |
| Energia | 177636 | 176622 |
| **Energia por entrega** | **15,49** | **15,40** |

**Por tipo de assinante** (com falha):

| Assinante | Entregas | Latência média | p95 | Saltos médios |
|---|---|---|---|---|
| Nó do Core | 8021 | 0,05 s | 0,08 s | 4,27 |
| Satélite | 3450 | 14,50 s | 30,24 s | 6,38 |

---

## 8. Discussão

- **Nenhuma perda, com ou sem falha:** MDR de 100%, sem falsos negativos e sem
  duplicatas.
  - **Custo das 119 falhas:** 407 retransmissões e +0,6% de energia por
    entrega.
  - **Latência:** a média muda em menos de 0,01 s.
- **A falha raramente atinge um dado em trânsito:** um dado só anda pela
  árvore quando há rota, e o percurso entre nós do Core leva ~0,05 s. A falha
  pesa mais sobre os anúncios, e é aí que entra o SYNC.
  - **Teste controlado, à parte da rodada padrão** (tráfego do T1, falha
    periódica desligada): C2 foi derrubado de 197 a 198 s, quando o REACH de
    S2 passaria por ele.
  - **Sem os mecanismos da seção 4.3:** a mensagem para S2 esperou o próximo
    acoplamento de S2 (30,0 s).
  - **Com eles:** ela chegou em 6,95 s, logo depois de C2 voltar, porque o
    SYNC recuperou o REACH perdido.
- **A recuperação é rápida:** a tabela volta em 0,087 s em média, que é o
  tempo do primeiro beacon depois da falha. A recuperação dos dados (0,92 s,
  até 10 s) mede, na verdade, quanto tempo leva até o próximo tráfego passar
  por aquele nó.
- **A latência alta vem dos satélites, não do Pub/Sub:**
  - **Assinante no Core:** ~0,05 s.
  - **Assinante satélite:** espera o próximo acoplamento (média 14,5 s,
    p95 30,2 s); o p95/p99 geral reflete isso.
  - Com o rádio de 30 m e satélites que só falam no acoplamento, nenhum
    protocolo entrega antes de o satélite acoplar.
- **Os 89 falsos positivos vêm da convergência de assinatura:**
  - **Causa:** um satélite cria a assinatura longe do Core, e ela só chega a
    um PSPeer no próximo acoplamento. Até lá, o PSPeer usa o filtro antigo.
  - **Evidência:** todos os falsos positivos são de satélites com assinatura
    recente, e o número é o mesmo com e sem falha.
  - **Conclusão:** é o custo de não ter conhecimento global, não um erro de
    casamento. A convergência média, de 4,1 s, é dominada por esse atraso dos
    satélites.
- **Fora de ordem (3,1%):** publicações do mesmo autor podem ter donos
  diferentes, ou ficar guardadas em nós diferentes até o satélite acoplar, e
  seguem caminhos distintos. Garantir ordem exigiria numerar as publicações
  por autor e reordenar no assinante; não foi feito.
- **O custo está nas notificações:** cada publicação gera em média 6,7
  entregas, cada uma a ~4,9 saltos. O controle (63166) é dominado pelo HOP_ACK
  de cada dado, que é o preço da garantia de entrega sob falha.

---

## 9. Decisões de projeto e premissas

- **Transporte só pelo SwCore:** pedidos, `sync` e notificações vão salto a
  salto pela árvore, com o mesmo rádio de 30 m, como no slide 22. Não há
  rádio de longo alcance entre os nós do Core.
- **Três PSPeers (C1, C3, C7):** o líder e um nó a 2 saltos em cada asa
  cobrem todo o Core a ≤ 2 saltos (slide 22: PSPeer no líder e outros a até
  2 saltos). Mais PSPeers encurtariam os pedidos, mas multiplicariam os `sync`.
- **Dono da publicação:** evita duplicatas sem coordenação entre PSPeers. As
  réplicas guardam todas as publicações e assinaturas; o registro de "a quem
  já notifiquei" fica só no dono.
- **Sem histórico anterior à assinatura:** o assinante recebe o que for
  publicado a partir da assinatura. Entregar o histórico inteiro de um tópico a
  cada assinatura nova multiplicaria o tráfego.
- **Filtro vigente na criação da publicação:** a regra não depende de quando
  cada PSPeer fica sabendo das coisas. Por isso, ela também serve de gabarito
  para falso positivo e falso negativo.
- **Satélites publicam ao acoplar:** a publicação de satélite segue o ritmo do
  acoplamento, como a mensagem do T1. As assinaturas dos satélites são
  sorteadas a qualquer momento e esperam na fila até o acoplamento.
- **Falha com semente fixa:** a mesma sequência de falhas em todas as
  execuções, o que permite comparar com e sem falha.
- **HOP_ACK em 0,2 s:** é o intervalo dos beacons e muito maior que o atraso
  de 2 transmissões (0,02 s). Numa falha de 1 s, um remetente tenta no máximo
  ~5 vezes antes de o enlace marcar o vizinho como perdido.

---

## 10. Como reproduzir

```bash
python main.py 6 2          # Pub/Sub sem browser: gera results_pubsub.md e logs/pubsub.log
python main.py 6 1          # Pub/Sub no visualizador 3D (30× mais rápido)
```

- **Sem falha:** `CORE_FAILURE = False` em `src/config.py`.
- **Falha e Pub/Sub:** `FAILURE_*` (falha) e `PS_*` (Pub/Sub) em
  `src/config.py`.
- **Visualizador:** o nó em falha fica vermelho-escuro, e o painel mostra
  "Rádio: FALHA (incomunicável)".

## 11. Estrutura do código (T2)

| Arquivo | Conteúdo |
|---|---|
| `src/pubsub.py` | Estado dos PSPeers, regra de entrega, papéis de cliente e PSPeer, métricas de Pub/Sub |
| `src/routing/swcore_mixin.py` | SwCore com tabela do Core, SYNC, HOP_ACK e retransmissão |
| `src/scenario.py` | Falha de core (sorteio e janelas), PSPeers e distância na árvore, região de cada nó |
| `src/node.py` | Ponto único de saída do rádio (`_transmit`) e corte do rádio na falha |
| `src/metrics.py` | Tempo de recuperação após falha |
| `src/motor.py`, `main.py` | Opção 6 do menu e tabela `results_pubsub.md` |

## 12. Referências

- Slides da disciplina INF2541: Swarm Core, Pub/Sub distribuído (slides
  21–22) e métricas de avaliação (slides 23–24).
