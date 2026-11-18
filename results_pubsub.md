# Resultados do Pub/Sub sobre SwCore

| Métrica | Valor | Descrição |
| :--- | :---: | :--- |
| Publicações | 1721 | Publicações criadas (Core: sorteio a cada PS_INTERVAL s; satélites: uma por acoplamento). |
| Assinaturas | 459 | Assinaturas criadas; uma nova do mesmo tópico substitui o filtro anterior do nó. |
| Entregas esperadas | 11471 | Pares (assinante, publicação) que a regra de entrega exige: filtro vigente na criação da publicação contém a região dela; nunca ao próprio autor. |
| Entregues | 11471 | Entregas esperadas que chegaram ao assinante. |
| MDR (%) | 100.0 | Taxa de entrega: entregues / esperadas × 100. |
| Falsos positivos | 89 | Entregas que a regra não exigia (o PSPeer ainda não conhecia o filtro novo do assinante). |
| Falsos negativos | 0 | Entregas esperadas que não chegaram até o fim da simulação. |
| Duplicadas | 0 | Cópias extras da mesma publicação no mesmo assinante. |
| Fora de ordem | 359 | Entregas que chegaram depois de uma publicação mais nova do mesmo autor, para o mesmo assinante. |
| Fora de ordem (%) | 3.13 | Fora de ordem / entregas esperadas × 100 (sem falsos positivos). |
| Latência média (s) | 4.40 | Da criação da publicação à entrega (só entregas esperadas). |
| Latência p95 (s) | 23.87 | Percentil 95 da latência. |
| Latência p99 (s) | 32.14 | Percentil 99 da latência. |
| Saltos médios | 4.90 | Transmissões de rádio do autor ao PSPeer e do PSPeer ao assinante. |
| Convergência de assinatura (s) | 4.109 | Da criação da assinatura até todos os PSPeers a conhecerem (média). |
| Vazão (entregas/min) | 191.2 | Entregas esperadas por minuto simulado. |
| Falhas de core | 119 | Janelas em que um nó do Core ficou incomunicável (1 s a cada 30 s). |
| Recuperação do roteamento (s) | 0.087 | Do fim da falha até o core e todos os vizinhos da árvore trocarem SYNC (média). |
| Recuperação do roteamento, máx. (s) | 0.220 | Pior caso da linha anterior. |
| Recuperação dos dados (s) | 0.920 | Do fim da falha até o 1º dado confirmado (HOP_ACK) enviado pelo core ou a ele (média; depende do tráfego). |
| Recuperação dos dados, máx. (s) | 10.250 | Pior caso da linha anterior. |
| Retransmissões por salto | 407 | Dados reenviados por falta de HOP_ACK (ex.: próximo salto em falha). |
| Tx dados | 55388 | Pacotes de dados transmitidos (pedidos, syncs e notificações). |
| Tx controle | 63166 | Pacotes de controle: REACH/UNREACH, SYNC e HOP_ACK. |
| Energia | 177636 | 1 por transmissão + 0,5 por recepção (unidades arbitrárias). |
| Energia por entrega | 15.49 | Energia / entregas esperadas. |
