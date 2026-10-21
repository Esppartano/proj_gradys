# Resultados

| Protocolo | Criadas | Entregues | PDR% | Lat. média(s) | Lat. mediana(s) | Lat. máx.(s) | Saltos médios | Tx dados | Msgs dados tx | Tx controle | Tx / entrega | Rx redund. | Entregas dupl. | Desc. TTL | Podas | Contornos | Sem rota | ACKs origem | Energia |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| flooding | 472 | 0 | 0.0 | n/d | n/d | n/d | n/d | 4248 | 4248 | 0 | n/d | 3304 | 0 | 0 | 472 | 0 | 0 | 0 | 8732 |
| geocast | 472 | 0 | 0.0 | n/d | n/d | n/d | n/d | 3776 | 3776 | 3304 | n/d | 0 | 0 | 0 | 0 | 0 | 472 | 0 | 12036 |
| dtn | 472 | 472 | 100.0 | 17.95 | 17.90 | 30.20 | 6.00 | 4485 | 4720 | 12514 | 36.01 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 29280 |
| swcore | 472 | 472 | 100.0 | 18.03 | 17.98 | 30.20 | 6.00 | 2832 | 2832 | 7680 | 22.27 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 15768 |

## Legenda

- **Protocolo**: Protocolo de roteamento usado.
- **Criadas**: Mensagens criadas pelos satélites (uma por acoplamento, para o satélite do eixo oposto); igual em todos.
- **Entregues**: Mensagens que chegaram ao destino (só a primeira chegada conta).
- **PDR%**: Taxa de entrega: entregues / criadas × 100. Mede a eficácia.
- **Lat. média(s)**: Tempo médio entre criar e entregar (só das entregues).
- **Lat. mediana(s)**: Mediana desse tempo (menos sensível a extremos).
- **Lat. máx.(s)**: Maior tempo entre criar e entregar.
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
- **Energia**: Energia de rádio: 1 por transmissão + 0,5 por recepção (unidades arbitrárias).
