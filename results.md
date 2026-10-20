# Resultados

| Protocolo | Criadas | Entregues | PDR% | Lat. média(s) | Lat. mediana(s) | Saltos médios | Tx dados | Msgs dados tx | Tx controle | Tx / entrega | Rx redund. | Entregas dupl. | Desc. TTL | Podas | Contornos | Sem rota | ACKs origem | Expiradas | Energia |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| flooding | 165 | 44 | 26.7 | 39.38 | 37.37 | 5.43 | 1365 | 1365 | 313 | 38.14 | 1553 | 42 | 0 | 499 | 0 | 0 | 44 | 0 | 3664 |
| geocast | 165 | 44 | 26.7 | 39.39 | 37.37 | 5.48 | 778 | 778 | 1320 | 47.68 | 8 | 0 | 0 | 4 | 42 | 116 | 0 | 0 | 3964 |
| dtn | 165 | 165 | 100.0 | 77.85 | 75.34 | 4.68 | 663 | 1967 | 1536 | 13.33 | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3748 |
| swcore | 165 | 165 | 100.0 | 81.52 | 81.44 | 6.22 | 1026 | 1026 | 224 | 7.58 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1875 |

## Legenda

- **Protocolo**: Protocolo de roteamento usado.
- **Criadas**: Mensagens de dados criadas pelos endpoints (satélites e BS); igual em todos.
- **Entregues**: Mensagens que chegaram ao destino (só a primeira chegada conta).
- **PDR%**: Taxa de entrega: entregues / criadas × 100. Mede a eficácia.
- **Lat. média(s)**: Tempo médio entre criar e entregar (só das entregues).
- **Lat. mediana(s)**: Mediana desse tempo (menos sensível a extremos).
- **Saltos médios**: Transmissões de rádio que a mensagem entregue percorreu, em média.
- **Tx dados**: Pacotes de dados transmitidos (um lote do DTN conta como 1).
- **Msgs dados tx**: Mensagens de dados transmitidas, contando cada uma dentro dos lotes do DTN.
- **Tx controle**: Pacotes de controle do protocolo: avisos de alcance (SwCore), vetores-resumo (DTN), ACKs do receptor (Flooding), buscas e respostas de rota (GeoCast). Beacons de formação ficam de fora.
- **Tx / entrega**: (Tx dados + Tx controle) / entregues: custo em transmissões de cada entrega. Mede a eficiência.
- **Rx redund.**: Vezes que um nó recebeu uma mensagem que já tinha visto (desperdício).
- **Entregas dupl.**: Cópias extras da mesma mensagem que chegaram ao destino.
- **Desc. TTL**: Mensagens descartadas por esgotar o limite de saltos (Flooding/GeoCast).
- **Podas**: Retransmissões evitadas: self-pruning no Flooding (todos os vizinhos já foram cobertos) ou nó fora da zona-alvo no GeoCast.
- **Contornos**: GeoCast: vazios de cobertura contornados pela busca de rota (Choi et al.).
- **Sem rota**: GeoCast: mensagens descartadas num vazio de cobertura que a busca de rota não conseguiu contornar.
- **ACKs origem**: Flooding: confirmações do receptor que chegaram de volta à origem.
- **Expiradas**: Mensagens nunca entregues cuja espera venceu: retenção no SwCore ou cópias no DTN.
- **Energia**: Energia de rádio: 1 por transmissão + 0,5 por recepção (unidades arbitrárias).
