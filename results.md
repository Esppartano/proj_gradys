# Resultados

| Protocolo | Criadas | Entregues | PDR% | Lat. média(s) | Lat. mediana(s) | Saltos médios | Tx dados | Msgs dados tx | Tx controle | Tx / entrega | Rx redund. | Entregas dupl. | Desc. TTL | Podas zona | Expiradas | Energia |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| flooding | 165 | 44 | 26.7 | 39.38 | 37.37 | 5.43 | 1737 | 1737 | 0 | 39.48 | 2148 | 84 | 0 | 0 | 0 | 3661 |
| geocast | 165 | 44 | 26.7 | 39.38 | 37.37 | 5.43 | 1278 | 1278 | 0 | 29.05 | 1514 | 84 | 0 | 148 | 0 | 2730 |
| dtn | 165 | 165 | 100.0 | 88.90 | 87.16 | 4.81 | 286 | 802 | 5868 | 37.30 | 0 | 0 | 0 | 0 | 0 | 11372 |
| swcore | 165 | 165 | 100.0 | 81.52 | 81.44 | 6.22 | 1026 | 1026 | 224 | 7.58 | 0 | 0 | 0 | 0 | 0 | 1875 |

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
- **Tx controle**: Pacotes de controle do protocolo: avisos de alcance (SwCore), resumos e ACKs (DTN). Beacons de formação ficam de fora.
- **Tx / entrega**: (Tx dados + Tx controle) / entregues: custo em transmissões de cada entrega. Mede a eficiência.
- **Rx redund.**: Vezes que um nó recebeu uma mensagem que já tinha visto (desperdício).
- **Entregas dupl.**: Cópias extras da mesma mensagem que chegaram ao destino.
- **Desc. TTL**: Mensagens descartadas por esgotar o limite de saltos (Flooding/GeoCast).
- **Podas zona**: Retransmissões evitadas por o nó estar fora da zona de encaminhamento (GeoCast).
- **Expiradas**: Mensagens guardadas que passaram do tempo máximo de espera (SwCore).
- **Energia**: Energia de rádio: 1 por transmissão + 0,5 por recepção (unidades arbitrárias).
