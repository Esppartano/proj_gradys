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
