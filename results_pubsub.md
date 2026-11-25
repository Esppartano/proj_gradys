# Resultados do Pub/Sub sobre o SwCore do professor

| Métrica | Valor | Descrição |
| :--- | :---: | :--- |
| MDR (%) | 97.67 | Publicações que chegaram a TODOS os assinantes elegíveis / publicações com ao menos um elegível × 100. |
| Fora de ordem (%) | 0.12 | Entregas que chegaram depois de uma publicação mais nova do mesmo autor, no mesmo tópico, para o mesmo assinante / entregues × 100. |
| Latência média (s) | 19.10 | Da publicação à entrega, só publicações posteriores à assinatura (ao vivo). Inclui o tempo que a publicação de um satélite espera nele até acoplar e o que a entrega a um satélite espera até ele acoplar. |
| Latência p95 (s) | 41.15 | Percentil 95 da latência ao vivo. |
| Latência p99 (s) | 61.95 | Percentil 99 da latência ao vivo. |
| Recuperação após falha, média (s) | 0.19 | Entre as falhas recuperadas: do fim da falha até todo o Core ter de novo rota aos outros 8 nós, o PSPeer mais próximo de antes e as linhas de satélite iguais ao estado real (amostras a cada 0,1 s). |
| Recuperação após falha, máx. (s) | 0.30 | Pior caso da linha anterior. |
| Falhas recuperadas | 119 | Falhas recuperadas em até 10 s (de `Falhas de core`). |
| Falhas de core | 119 | Janelas em que um nó do Core ficou incomunicável (1 s a cada 30 s) e cuja medição coube na simulação (terminou até 10 s antes do fim ou recuperou antes). |
| Publicações | 2616 | Publicações criadas: Core (sorteio a cada PS_INTERVAL s) e satélites (uma por sensor encontrado em cada viagem). |
| Publicações de satélites | 1398 | Das publicações, as de satélites (sensor par → T2, ímpar → T1). |
| Publicações com assinante elegível | 2616 | Base do MDR: publicações com ao menos um assinante cujo filtro contém a região delas. |
| Assinaturas | 26 | Assinaturas criadas (cada nó assina cada tópico no máximo uma vez). |
| Entregas esperadas | 22241 | Pares (assinante, publicação): o assinante assina o tópico com filtro que contém a região da publicação (inclusive a fila anterior à assinatura); nunca ao próprio autor. |
| Entregues | 22059 | Entregas esperadas que chegaram. |
| Taxa por par (%) | 99.18 | Entregues / esperadas × 100. |
| Falsos positivos | 0 | Entregas que a regra não exigia (filtro ou tópico errado). |
| Duplicadas | 0 | Cópias extras da mesma publicação no mesmo assinante (descartadas por ele). |
| Entregas ao vivo | 17377 | Entregas de publicações posteriores à assinatura (base da latência). |
| Entregas da fila antiga | 4682 | Entregas de publicações anteriores à assinatura. |
| Latência da fila antiga (s) | 6.88 | Da assinatura à entrega, para a fila antiga (média). |
| Saltos médios | 5.35 | Transmissões de rádio do autor ao PSPeer, entre PSPeers (sync) e do PSPeer ao assinante. |
| Convergência de assinatura (s) | 5.278 | Da criação da assinatura até os 3 PSPeers a conhecerem (média). Inclui o tempo até o satélite acoplar. |
| Assinaturas não sincronizadas | 0 | Assinaturas que algum PSPeer nunca conheceu (sync perdido numa falha; sem retransmissão). |
| Vazão (entregas/min) | 367.6 | Entregues por minuto simulado. |
| Tx dados | 9811 | Pacotes de dados: pedidos ao PSPeer, entregas aos assinantes e dados do SwCore até os satélites. |
| Tx controle | 21190 | Pacotes de controle: atualizações e pedidos da RT de satélites do SwCore, confirmações de upload e syncs entre PSPeers. Beacons de enlace (inclusive os que levam a RT do Core) ficam de fora, como no T1. |

## Energia (extra, não exigida pelo enunciado)

Critério de medição (extra; o enunciado do T2 não pede energia):

- **Comunicação:** cada pacote transmitido pelo nó conta 1 e cada pacote recebido
  conta 0,5 (`E_TX`, `E_RX` em `src/config.py`); um broadcast conta uma recepção por
  ouvinte, e um unicast só chega ao destinatário (o GrADySim não entrega a terceiros ao
  alcance). O nó em falha não transmite nem recebe. Unidade relativa (não joules),
  a mesma do T1. Classes de pacote:
  - **protocolo:** Pub/Sub e SwCore (pedidos, entregas, syncs, RT de satélites,
    confirmações de upload);
  - **enlace:** beacons periódicos e disparados por mudança de rota, e handshake de
    acoplamento (`link*`); no SwCore do professor, os beacons do Core levam a RT do Core;
  - **coleta:** leituras entregues pelos sensores aos satélites (`sensor_data`).
- **Voo:** distância = soma dos deslocamentos entre telemetrias consecutivas (a cada
  0,05 s); tempo em movimento = soma dos intervalos com deslocamento
  > 1 mm. Dados brutos, sem coeficientes físicos (o gasto por metro
  depende do drone).

### Por papel (média por nó)

| Papel (nós) | E protocolo | E enlace | E coleta | E total | Tx / Rx protocolo | Distância (m) | Em movimento (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| PSPeer (3) | 7122 | 38305 | 0 | 45427 | 5119 / 4006 | 15757 | 3596 |
| Core (não PSPeer) (6) | 4988 | 35000 | 0 | 39988 | 2458 / 5062 | 15464 | 3595 |
| Satélite (4) | 436 | 21982 | 900 | 23319 | 225 / 422 | 9568 | 1914 |
| Sensor (12) | 1 | 7872 | 600 | 8473 | 0 / 1 | 0 | 0 |

### Por nó

| Nó | E protocolo | E enlace | E coleta | E total | Tx / Rx protocolo | Distância (m) | Em movimento (s) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| C1 (PSPeer) | 8603 | 36444 | 0 | 45048 | 6198 / 4810 | 9610 | 3600 |
| C2 (Core (não PSPeer)) | 5988 | 36455 | 0 | 42442 | 2994 / 5987 | 8130 | 3596 |
| C3 (Core (não PSPeer)) | 5540 | 36502 | 0 | 42041 | 2943 / 5193 | 12386 | 3595 |
| C4 (PSPeer) | 6014 | 39784 | 0 | 45797 | 4248 / 3531 | 18824 | 3596 |
| C5 (Core (não PSPeer)) | 3092 | 32140 | 0 | 35232 | 1366 / 3451 | 25866 | 3595 |
| C6 (Core (não PSPeer)) | 6192 | 36418 | 0 | 42611 | 2978 / 6429 | 8130 | 3596 |
| C7 (Core (não PSPeer)) | 5788 | 36366 | 0 | 42154 | 3028 / 5519 | 12391 | 3594 |
| C8 (PSPeer) | 6749 | 38686 | 0 | 45436 | 4910 / 3678 | 18835 | 3593 |
| C9 (Core (não PSPeer)) | 3331 | 32116 | 0 | 35446 | 1436 / 3790 | 25879 | 3592 |
| S1 (Satélite) | 418 | 22052 | 900 | 23370 | 217 / 403 | 9532 | 1906 |
| S2 (Satélite) | 444 | 21916 | 901 | 23262 | 234 / 421 | 9612 | 1922 |
| S3 (Satélite) | 429 | 22046 | 900 | 23374 | 213 / 432 | 9542 | 1908 |
| S4 (Satélite) | 453 | 21916 | 900 | 23270 | 236 / 434 | 9587 | 1917 |
| X13 (Sensor) | 2 | 10426 | 720 | 11148 | 0 / 4 | 0 | 0 |
| X14 (Sensor) | 0 | 9546 | 720 | 10266 | 0 / 0 | 0 | 0 |
| X15 (Sensor) | 0 | 3705 | 359 | 4064 | 0 / 0 | 0 | 0 |
| X16 (Sensor) | 0 | 10317 | 720 | 11037 | 0 / 0 | 0 | 0 |
| X17 (Sensor) | 0 | 9540 | 720 | 10260 | 0 / 0 | 0 | 0 |
| X18 (Sensor) | 0 | 3736 | 362 | 4098 | 0 / 0 | 0 | 0 |
| X19 (Sensor) | 6 | 10414 | 720 | 11140 | 0 / 11 | 0 | 0 |
| X20 (Sensor) | 0 | 9546 | 720 | 10266 | 0 / 0 | 0 | 0 |
| X21 (Sensor) | 0 | 3678 | 359 | 4037 | 0 / 0 | 0 | 0 |
| X22 (Sensor) | 0 | 10316 | 720 | 11036 | 0 / 0 | 0 | 0 |
| X23 (Sensor) | 0 | 9540 | 720 | 10260 | 0 / 0 | 0 | 0 |
| X24 (Sensor) | 0 | 3700 | 361 | 4062 | 0 / 0 | 0 | 0 |
