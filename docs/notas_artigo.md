# Notas de pesquisa: artigo (leitmotiv D)

**Tema escolhido:** *D — Global Path Planning and energy management strategies for
swarm of UAVs*.

**Status:** passo 1 de 4 feito (levantamento das fontes); lista enviada ao professor em 25/11/2026, aguardando retorno. Este
trabalho é separado do T2: o relatório do T2 não cita o artigo.

| Passo | Conteúdo | Status |
|---|---|---|
| 1 | Levantar as fontes sugeridas | feito |
| 2 | Consolidar o que já foi escolhido e pesquisado | a fazer |
| 3 | Relação com o T1/T2 | a fazer (prévia abaixo) |
| 4 | Foco e estrutura da apresentação e da monografia | a fazer (decisão do autor) |

Legenda de leitura: **lido** = texto completo lido; **localizado** = só título,
resumo ou trechos de busca. Números só aparecem aqui quando vêm do texto lido.

---

## Lista enviada ao professor (25/11/2026), aguardando retorno

Autores conferidos na API do arXiv, no NCBI E-utilities e, para o item 6, nos
metadados do PDF e no repositório da BIU. Coluna "Pasta": ✔ = PDF em
`docs/referencias/leitmotiv/` (fora do git).

| # | Grupo | Referência | Pasta |
|---|---|---|---|
| 1 | A: indicada no texto | Qi, Y.; Jiang, H.; Huang, G.; Yang, L.; Wang, F.; Xu, Y. "Multi-UAV path planning considering multiple energy consumptions via an improved bee foraging learning particle swarm optimization algorithm". *Scientific Reports* 15, 14755 (2025). [PMC12037825](https://pmc.ncbi.nlm.nih.gov/articles/PMC12037825/) | ✔ |
| 2 | B: MARL (MAHPPO-AM) | Sun, T.; Guo, N.; Gu, H.; Peng, Y.; Feng, Z. "Integrated Communication and Control for Energy-Efficient UAV Swarms: A Multi-Agent Reinforcement Learning Approach". [arXiv:2509.23905](https://arxiv.org/pdf/2509.23905) (2025) | ✔ |
| 3 | B: MARL (DDPG, ator-crítico) | Alam, M. M.; Aarafat, M. Y.; Hossain, T. "Variations in Multi-Agent Actor-Critic Frameworks for Joint Optimizations in UAV Swarm Networks: Recent Evolution, Challenges, and Directions". [arXiv:2410.06627](https://arxiv.org/pdf/2410.06627) (2024) | ✔ |
| 4 | B: enxame / trajetória | Arshid, K.; Krayani, A.; Marcenaro, L.; Gomez, D. M.; Regazzoni, C. "Toward Autonomous UAV Swarm Navigation: A Review of Trajectory Design Paradigms". *Sensors* 25(18) (2025). DOI 10.3390/s25185877. [PMC12473296](https://pmc.ncbi.nlm.nih.gov/articles/PMC12473296/) | ✔ |
| 5 | B: rodízio e recarga | Arribas, E.; Cholvi, V.; Mancuso, V. "Optimizing UAV Recharge Scheduling for Heterogeneous and Persistent Aerial Service". [arXiv:2205.12656](https://arxiv.org/pdf/2205.12656) (2022) | ✔ |
| 6 | B: drones reserva | Hartuv, E.; Kraus, S.; Agmon, N. "Spare Drone Optimization for Persistent Task Performance with Multiple Homes". ICUAS 2020, pp. 389–397. [PDF](https://u.cs.biu.ac.il/~agmon/HartuvICUAS20.pdf) (ordem dos autores: conferir na 1ª página) | ✔ |
| 7 | B: troca de bateria | Bouček, Z.; Flídr, M.; Straka, O. "Mission Planner for UAV Battery Replacement". [arXiv:2407.01084](https://arxiv.org/pdf/2407.01084) (2024) | ✔ |
| 8 | C: modelo de energia | Beigi, P.; Rajabi, M. S.; Aghakhani, S. "An Overview of Drone Energy Consumption Factors and Models". [arXiv:2206.10775](https://arxiv.org/pdf/2206.10775) (2022) | ✔ |
| 9 | C: modelo de energia | Muli, C.; Park, S.; Liu, M. "A Comparative Study on Energy Consumption Models for Drones". [arXiv:2206.01609](https://arxiv.org/pdf/2206.01609) (2022) | ✔ |
| 10 | D: paga | Chen, X.; Tianfield, H.; Du, W. "Bee-foraging learning particle swarm optimization". *Applied Soft Computing* 102 (2021). [DOI](https://doi.org/10.1016/j.asoc.2021.107134) | — |
| 11 | D: paga | Kamra, N.; Kumar, T. K. S.; Ayanian, N. "Combinatorial Problems in Multirobot Battery Exchange Systems". *IEEE T-ASE* 15(2), 852–862 (2018). [DOI](https://doi.org/10.1109/TASE.2017.2767379) | — |
| 12 | D: paga | Li, H.; Zhan, Z.; Wang, Z. "Energy-consumption model for rotary-wing drones". *J. Field Robotics* 41, 1940–1959 (2024). [DOI](https://doi.org/10.1002/rob.22359) | — |

Grupos:
- **A:** indicada no texto do tema.
- **B:** escolhidas por nós para cobrir as abordagens que o texto cita sem dar
  referência.
- **C:** acrescentadas para o modelo de energia.
- **D:** pagas; perguntamos ao professor se são necessárias. Na rede da PUC
  devem abrir.

**Leitura até agora:** só 1 e 2 foram lidas por inteiro, nas seções abaixo. As
demais foram localizadas.

---

## Fontes sugeridas no tema

1. **Artigo de partida:** Yuanhang Q. et al., 2025, Scientific Reports (seção 1).
2. **MARL (aprendizado por reforço multiagente):** DDPG, MAHPPO-AM (seção 2).
3. **Inteligência de enxame:** PSO, GA, forrageamento de abelhas (seção 1,
   que já compara essas técnicas).
4. **Escalonamento rotativo e reabastecimento:** rodízio de drones e troca de
   bateria em estação de solo (seção 3).

---

## 1. Artigo-base: Qi et al. (2025) — lido

**Referência:** Qi, Y.; Jiang, H.; Huang, G.; Yang, L.; Wang, F.; Xu, Y.
"Multi-UAV path planning considering multiple energy consumptions via an
improved bee foraging learning particle swarm optimization algorithm".
*Scientific Reports* 15, 14755 (2025). DOI
[10.1038/s41598-025-99001-z](https://doi.org/10.1038/s41598-025-99001-z).
Acesso aberto (CC BY-NC-ND); cópia no
[PMC12037825](https://pmc.ncbi.nlm.nih.gov/articles/PMC12037825/).

### Problema (MUAVPP-MEC)

- K drones partem de um ponto central e visitam pontos de coleta de dados IoT
  em altitudes diferentes (0–150 m, sorteadas); cada ponto é atendido por um só
  drone.
- **Objetivo:** minimizar o tempo total de voo (Eq. 1).
- **Restrição:** a energia de cada drone não passa da bateria (Eq. 7).
- **Tipo:** roteamento de veículos (MINLP), resolvido de forma **centralizada e
  offline**.

### Modelo de energia (só propulsão)

| Parcela | Modelo | Fonte no artigo |
|---|---|---|
| Distância | Aceleração e desaceleração fixas (1 m/s², 112,5 m e 15 s cada; 6096,3 J e 4944,2 J) + voo em velocidade constante (15 m/s a 429,87 W) | Eq. 8, Tab. 1 |
| Curva | Linear no ângulo de giro: 5,3316·θ + 104,65 J (ajuste de dados experimentais) | Eq. 9–10, ref. 17 |
| Subida | M·g·Δh / η, com M = 3,8 kg, η = 0,74; descer não custa | Eq. 11 |

- **Drone simulado:** hexacóptero X4108.
- **Bateria:** 10.000 mAh a 11,1 V, ou seja, 399.600 J.
- **Carga útil:** os autores notam que ela aumentaria todas as parcelas.

### Algoritmo IBFLPSO

- **Base:** BFL-PSO (Chen et al., 2021), PSO com três estágios inspirados no
  forrageamento de abelhas:
  1. aprendizado, como no PSO;
  2. reforço das regiões das melhores partículas;
  3. "escoteiras", que reiniciam partículas estagnadas.
- **Codificação:** números reais, decodificados pela divisão gulosa da sequência
  de pontos entre os drones, conforme a energia disponível.
- **Busca local:** 2-opt com restrição de energia.

### Resultados (Tab. 4; 51 pontos, 40 partículas, 500 iterações, 10 execuções)

| Comparado com | Tempo de voo (melhor solução) | Energia (melhor solução) |
|---|---|---|
| PSO | −54,64% | −53,21% |
| PSO-2OPT | −49,45% | −48,04% |
| GA | −25,78% | −24,80% |
| BFLPSO | −22,92% | −21,99% |

- **Atenção:** os percentuais do resumo medem **tempo de voo**, não energia.
- **Custo computacional:** 113,5 s por execução, contra 0,84 s do GA e 27,6 s do
  BFLPSO.

### O que o artigo não trata (verificado no texto)

- comunicação entre drones, rede, formação ou energia de comunicação (só cita,
  de passagem, um trabalho que considera comunicação);
- recarga, troca de bateria, replanejamento dinâmico ou execução
  descentralizada.
- O único trabalho futuro declarado é considerar a carga útil.

### Referências do artigo para ler em seguida

- [24] Chen, Tianfield, Du. "Bee-foraging learning particle swarm optimization".
  *Applied Soft Computing* 102 (2021). DOI 10.1016/j.asoc.2021.107134 —
  algoritmo de base.
- [17] Dong, Wu, Zhu, Li. "Energy-efficient flight planning for UAV in IoT
  environment". *J. Southeast Univ.* 50 (2020) — origem do modelo de curva.
- [32] Li, Zhan, Wang. "Energy-consumption model for rotary-wing drones".
  *J. Field Robotics* 41 (2024). DOI 10.1002/rob.22359 — modelo de energia de
  multirrotor.
- [29] Zorbas et al. "Energy efficient mobile target tracking using flying
  drones". *Procedia Comput. Sci.* 19 (2013) — energia de subida.

---

## 2. MARL: MAHPPO-AM (Sun et al., 2025) — lido

**Referência:** Sun, T.; Guo, N.; Gu, H.; Peng, Y.; Feng, Z. "Integrated
Communication and Control for Energy-Efficient UAV Swarms: A Multi-Agent
Reinforcement Learning Approach". Preprint
[arXiv:2509.23905](https://arxiv.org/abs/2509.23905) (2025).

- **Cenário:** 3 drones como estações-base aéreas atendendo 9 usuários em solo
  (OFDMA downlink, canal 3GPP), em 60 passos de 1 s.
- **Problema:** maximizar a eficiência energética com justiça entre usuários
  (índice de Jain).
  - **Variáveis:** trajetória 3D, velocidade, potência e alocação de canal.
  - **Restrições:** distância mínima de 25 m entre drones, limites de
    velocidade, aceleração e altitude, e potência total.
- **Energia:** só propulsão (em função da velocidade e da aceleração). A de
  comunicação é desprezada, por ser "duas ordens de grandeza menor que a de voo"
  segundo os autores.
- **Método:** PPO multiagente com ações híbridas (discretas e contínuas), com
  *action masking* para as restrições discretas e um crítico global. Os agentes
  recebem o **estado global**, então a execução não é descentralizada de fato.
- **Resultado:** energia média de 14,88 kJ contra 19,86 kJ do HPPO, cerca de 25%
  a menos (média de 100 execuções; o "up to 25%" do texto exagera um pouco).
- **Ressalvas:**
  - um único cenário pequeno;
  - baselines fracos (HPPO e uma variante sem aprendizado), sem DDPG/MADDPG;
  - sem seção de limitações.
- **Referências citadas para ler em seguida:**
  - Liu et al., IEEE JSAC 36(9), 2018 (energia com justiça);
  - Bai et al., "MA-HPPO for multi-UAV data collection", IEEE TWC 23(12), 2024;
  - Yin e Yu, IEEE IoT J. 9(4), 2022.

---

## 3. Outras frentes — localizadas, não lidas

| Frente | Fonte | Por que ler |
|---|---|---|
| MARL (DDPG, MADDPG) | [Variations in Multi-Agent Actor-Critic Frameworks for Joint Optimizations in UAV Swarm Networks (arXiv 2410.06627)](https://arxiv.org/pdf/2410.06627) | Revisão dos métodos ator-crítico multiagente em enxames |
| Planejamento de trajetória de enxames | [Toward Autonomous UAV Swarm Navigation: A Review of Trajectory Design Paradigms](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12473296/) | Revisão (2025) que trata o problema como mTSP |
| Recarga e rodízio | [Optimizing UAV Recharge Scheduling for Heterogeneous and Persistent Aerial Service (arXiv 2205.12656)](https://arxiv.org/pdf/2205.12656) | Serviço contínuo com o mínimo de drones |
| Drones reserva | [Hartuv et al., ICUAS 2020](https://u.cs.biu.ac.il/~agmon/HartuvICUAS20.pdf) | Mínimo de drones reserva e escala de substituição |
| Troca de bateria + roteamento | [Kamra et al., IEEE TASE 2018](https://act.usc.edu/publications/Kamra_TASE2018.pdf) | Escalonamento de troca e planejamento de rota juntos |
| Modelos de energia | [An Overview of Drone Energy Consumption Factors and Models (arXiv 2206.10775)](https://arxiv.org/pdf/2206.10775) | Base para escolher um modelo de energia de voo |

**Lacuna notada na busca:** nenhuma dessas fontes de recarga trata de manter a
**conectividade da rede** do enxame durante as trocas.

---

## 4. Prévia da relação com o T1/T2 (opinião, a discutir no passo 3)

- **Mesmo cenário de coleta:** os satélites do T2 coletando leituras dos
  sensores fazem o mesmo papel dos drones do artigo-base, que coletam de pontos
  IoT. Só que no T2 a rota é fixa e não há planejamento.
- **Lacuna de comunicação:** o artigo-base ignora a comunicação, e o MAHPPO-AM a
  despreza. No T2 medimos o rádio por nó (`results_pubsub.md`, seção de
  energia): nos nós do Core, 81–91% é beacon de enlace. Só que a unidade é
  relativa, então ainda não dá para comparar com joules de voo.
- **Ganchos para rodízio de papéis:**
  - um PSPeer gasta cerca de 14% a mais de energia de rádio que os demais nós do
    Core;
  - as pontas do V voam cerca de 3× mais (25,9 km contra 8,1 km em 60 min) que
    os nós perto do centro de rotação.
- **Falha periódica de nó:** o T2 simula um nó do Core incomunicável por 1 s a
  cada 30 s, parecido com um drone que sai para trocar a bateria. A diferença é
  que lá o drone some de vez e não há reposição.
