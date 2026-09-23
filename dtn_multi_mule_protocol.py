from typing import Optional
from base_protocol import BaseFANETProtocol, METRICS
from messages import Packet, PacketType
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import Position


class DTNMultiMuleProtocol(BaseFANETProtocol):
    """
    Protocolo DTN Multi-Mula baseado em Arsheen et al. (2020) com Cadeia de Rendezvous.
    Suporte completo a cores dinâmicas RGB (0-255), tempos de permanência (Loiter) nos
    pontos de encontro e telemetria rastreada na interface 3D do GrADyS-SIM.
    """

    RENDEZVOUS_POINT: Position = (55.0, 0.0, 15.0)
    BASE_POINT: Position = (2.0, 0.0, 15.0)
    DEST_POINT: Position = (115.0, 0.0, 15.0)

    # Cores RGB de Alto Contraste (Three.js 0-255)
    COLOR_BASE_IDLE = (20, 60, 220)          # Azul Royal Profundo (Base P)
    COLOR_BASE_SUCCESS = (0, 255, 80)        # Verde Limão Neon (Concluído)
    COLOR_MULE_Q_IDLE = (220, 225, 230)      # Branco Metálico Claro (Mula Q)
    COLOR_MULE_R_IDLE = (160, 32, 240)       # Roxo / Púrpura Vibrante (Mula R)
    COLOR_CARRY_DATA = (255, 120, 0)         # Laranja Solar Vivo (Transportando Dados)
    COLOR_LOITER_RENDEZVOUS = (255, 230, 0)  # Amarelo Ouro / Neon (Handshake no Rendezvous)
    COLOR_CARRY_ACK = (0, 255, 255)          # Ciano Elétrico Puro (Transportando ACK)
    COLOR_DEST_WAITING = (255, 20, 50)       # Vermelho Intenso (Destino)
    COLOR_DEST_RECEIVED = (0, 255, 80)       # Verde Limão Neon
    COLOR_SPARSE_NODE = (80, 80, 90)         # Grafite Neutro (Nós isolados S e T)
    COLOR_FINISHED = (0, 255, 80)            # Verde Limão Neon de conclusão

    def __init__(self):
        super().__init__()
        self.state: str = "IDLE"

    def initialize(self) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        self.show_node_id(True)
        self.resize_all_nodes(2.5)

        # Nó 0 = Base P
        if my_id == 0:
            self.set_node_color(self.COLOR_BASE_IDLE)
            self.set_tracked_variable("Papel", "Base P (0)")
            self.set_tracked_variable("Estado", "Aguardando disparo (3s)")
            self.provider.schedule_timer("p_send", now + 3.0)

        # Nó 1 = Mula Q
        elif my_id == 1:
            self.set_node_color(self.COLOR_MULE_Q_IDLE)
            self.set_tracked_variable("Papel", "Mula Q (1)")
            self.set_tracked_variable("Estado", "Pronta na Base P")

        # Nó 2 = Mula R
        elif my_id == 2:
            self.set_node_color(self.COLOR_MULE_R_IDLE)
            self.set_tracked_variable("Papel", "Mula R (2)")
            self.set_tracked_variable("Estado", "No Rendezvous (Aguardando Mula Q)")

        # Nó 3 = Destino
        elif my_id == 3:
            self.set_node_color(self.COLOR_DEST_WAITING)
            self.set_tracked_variable("Papel", "Destino (3)")
            self.set_tracked_variable("Estado", "Aguardando pacote Arsheen")

        # Nós 4 e 5 = Nós isolados (S e T)
        elif my_id in (4, 5):
            self.set_node_color(self.COLOR_SPARSE_NODE)
            self.set_tracked_variable("Papel", f"Nó Esparso ({my_id})")
            self.set_tracked_variable("Estado", "Fora da rota de rendezvous")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        super().handle_telemetry(telemetry)
        my_id = self.provider.get_id()

        if self.mission_completed:
            return

        # ----------------- Mula Q (Nó 1) -----------------
        if my_id == 1:
            if self.state == "FLYING_TO_RENDEZVOUS" and self.has_reached(self.RENDEZVOUS_POINT, tolerance=3.0):
                self.state = "AT_RENDEZVOUS_OUTBOUND"
                self.set_node_color(self.COLOR_LOITER_RENDEZVOUS)
                self.set_tracked_variable("Estado", "No Rendezvous (Repassando à Mula R)")
                self.log("Mula Q chegou ao Rendezvous (x=55). Repassando comando para Mula R...")
                for pkt in list(self.buffer):
                    self.send_broadcast(pkt.serialize())

            elif self.state == "FLYING_TO_BASE" and self.has_reached(self.BASE_POINT, tolerance=3.0):
                self.state = "AT_BASE_FINAL"
                self.set_node_color(self.COLOR_FINISHED)
                self.set_tracked_variable("Estado", "Na Base P (Entregando ACK Final)")
                self.log("Mula Q retornou à Base P! Descarregando ACK final com sucesso...")
                for pkt in list(self.buffer):
                    self.send_broadcast(pkt.serialize())

        # ----------------- Mula R (Nó 2) -----------------
        elif my_id == 2:
            if self.state == "FLYING_TO_DEST" and self.has_reached(self.DEST_POINT, tolerance=3.0):
                self.state = "AT_DEST_LOITER"
                self.set_node_color(self.COLOR_LOITER_RENDEZVOUS)
                self.set_tracked_variable("Estado", "No Destino: Handshake / Loiter (2.0s)")
                self.log("Mula R chegou à coordenada do Destino (x=115). Entregando comando...")
                for pkt in list(self.buffer):
                    self.send_broadcast(pkt.serialize())

            elif self.state == "FLYING_BACK_TO_RENDEZVOUS" and self.has_reached(self.RENDEZVOUS_POINT, tolerance=3.0):
                self.state = "AT_RENDEZVOUS_RETURN"
                self.set_node_color(self.COLOR_LOITER_RENDEZVOUS)
                self.set_tracked_variable("Estado", "No Rendezvous: Devolvendo ACK à Mula Q")
                self.log("Mula R retornou ao Rendezvous (x=55) com o ACK! Repassando à Mula Q...")
                for pkt in list(self.buffer):
                    self.send_broadcast(pkt.serialize())

    def handle_timer(self, timer: str) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        # ----------------- BASE P (Nó 0) -----------------
        if timer == "p_send" and my_id == 0:
            pkt = Packet(
                packet_id="CMD_ARSHEEN_01",
                packet_type=PacketType.DATA.value,
                source=0,
                destination=3,
                content="ORDEM_MULTI_MULA",
                ttl=10,
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_tracked_variable("Estado", "Comando emitido à Mula Q")
            self.log("Base P emitiu pacote para entrega via cadeia de Rendezvous Q -> R.")
            self.send_broadcast(pkt.serialize())

        # ----------------- Mula R decola para o Destino após Loiter no Rendezvous -----------------
        elif timer == "r_fly_to_dest" and my_id == 2:
            self.state = "FLYING_TO_DEST"
            self.set_node_color(self.COLOR_CARRY_DATA)
            self.set_tracked_variable("Estado", "Decolando rumo ao Destino (x=115)")
            self.log("Loiter de repasse concluído. Mula R voando ao Destino (x=115)...")
            self.fly_to(*self.DEST_POINT)

        # ----------------- Mula R retorna ao Rendezvous após Loiter no Destino -----------------
        elif timer == "r_return_to_rendezvous" and my_id == 2:
            self.state = "FLYING_BACK_TO_RENDEZVOUS"
            self.set_node_color(self.COLOR_CARRY_ACK)
            self.set_tracked_variable("Estado", "Retornando ao Rendezvous com ACK")
            self.log("Loiter no Destino encerrado. Mula R retornando ao Rendezvous (x=55)...")
            self.fly_to(*self.RENDEZVOUS_POINT)

        # ----------------- Mula Q retorna à Base após receber ACK no Rendezvous -----------------
        elif timer == "q_return_to_base" and my_id == 1:
            self.state = "FLYING_TO_BASE"
            self.set_node_color(self.COLOR_CARRY_ACK)
            self.set_tracked_variable("Estado", "Retornando à Base P com ACK")
            self.log("Loiter de encontro finalizado. Mula Q voando de volta à Base P (x=2)...")
            self.fly_to(*self.BASE_POINT)

    def handle_packet(self, message: str) -> None:
        pkt = Packet.deserialize(message)
        if pkt is None:
            return

        my_id = self.provider.get_id()
        now = self.provider.current_time()

        if pkt.packet_type == "FINISH":
            self.mission_completed = True
            self.set_node_color(self.COLOR_FINISHED)
            self.set_tracked_variable("Estado", "Concluído")
            return

        # -------------------------------------------------------------
        # 1. Chegada no Destinatário do Pacote
        # -------------------------------------------------------------
        if pkt.destination == my_id:
            if pkt.packet_id not in self.seen_packets:
                self.seen_packets.add(pkt.packet_id)

                # Nó 3 (Destino)
                if pkt.packet_type == PacketType.DATA.value and my_id == 3:
                    METRICS.data_delivered += 1
                    METRICS.delivery_latency = now - pkt.creation_time
                    METRICS.hops = pkt.hop_count + 1
                    self.set_node_color(self.COLOR_DEST_RECEIVED)
                    self.set_tracked_variable("Estado", f"Dado recebido ({METRICS.delivery_latency:.2f}s)")
                    self.log(f"DESTINO ALCANÇADO: Recebeu '{pkt.content}' em {METRICS.delivery_latency:.2f}s (Saltos: {METRICS.hops})!")

                    ack = Packet(
                        packet_id=f"ACK_{pkt.packet_id}",
                        packet_type=PacketType.ACK.value,
                        source=3,
                        destination=0,
                        content="ACK_SUCESSO_ARSHEEN",
                        ttl=10,
                        creation_time=pkt.creation_time,
                        hop_count=0
                    )
                    self.seen_packets.add(ack.packet_id)
                    METRICS.ack_sent += 1
                    self.log("Destino emitiu ACK para transporte reverso via Mula R.")
                    self.send_broadcast(ack.serialize())

                # Nó 0 (Base P)
                elif pkt.packet_type == PacketType.ACK.value and my_id == 0:
                    METRICS.ack_delivered += 1
                    METRICS.round_trip_time = now - pkt.creation_time
                    METRICS.mission_success = True
                    self.mission_completed = True
                    self.set_node_color(self.COLOR_BASE_SUCCESS)
                    self.set_tracked_variable("Estado", f"Missão Concluída (RTT={METRICS.round_trip_time:.2f}s)")
                    self.log(f"BASE P: MISSÃO CONCLUÍDA COM SUCESSO TOTAL! (RTT={METRICS.round_trip_time:.2f}s, Saltos={pkt.hop_count + 1})")

                    finish_pkt = Packet(
                        packet_id="FIN_01",
                        packet_type="FINISH",
                        source=0,
                        destination=-1,
                        content="END_OF_MISSION"
                    )
                    self.send_broadcast(finish_pkt.serialize())
            return

        # -------------------------------------------------------------
        # 2. Mula Q (Nó 1)
        # -------------------------------------------------------------
        if my_id == 1 and not self.mission_completed:
            # Coleta comando na Base e voa para o Rendezvous
            if pkt.packet_type == PacketType.DATA.value and not any(p.packet_id == pkt.packet_id for p in self.buffer):
                pkt.hop_count += 1
                self.buffer.append(pkt)
                self.state = "FLYING_TO_RENDEZVOUS"
                self.set_node_color(self.COLOR_CARRY_DATA)
                self.set_tracked_variable("Estado", "Levando Dado -> Rendezvous (x=55)")
                self.set_tracked_variable("Buffer", pkt.packet_id)
                self.log("Mula Q coletou comando da Base P. Voando ao Rendezvous (x=55)...")
                self.fly_to(*self.RENDEZVOUS_POINT)

            # Recebe ACK da Mula R no Rendezvous
            elif pkt.packet_type == PacketType.ACK.value and not any(p.packet_id == pkt.packet_id for p in self.buffer):
                pkt.hop_count += 1
                self.buffer = [pkt]
                self.set_node_color(self.COLOR_CARRY_ACK)
                self.set_tracked_variable("Estado", "ACK Coletado no Rendezvous! Loiter (2.0s)")
                self.set_tracked_variable("Buffer", pkt.packet_id)
                self.log("RENDEZVOUS: Mula Q coletou ACK de Mula R! Aguardando Loiter de 2.0s para retornar à Base...")
                self.provider.schedule_timer("q_return_to_base", now + 2.0)

        # -------------------------------------------------------------
        # 3. Mula R (Nó 2)
        # -------------------------------------------------------------
        if my_id == 2 and not self.mission_completed:
            # Recebe comando da Mula Q no Rendezvous
            if pkt.packet_type == PacketType.DATA.value and not any(p.packet_id == pkt.packet_id for p in self.buffer):
                pkt.hop_count += 1
                self.buffer = [pkt]
                self.set_node_color(self.COLOR_CARRY_DATA)
                self.set_tracked_variable("Estado", "Comando recebido no Rendezvous! Loiter (2.0s)")
                self.set_tracked_variable("Buffer", pkt.packet_id)
                self.log("RENDEZVOUS: Mula R recebeu comando de Mula Q! Aguardando Loiter de 2.0s para decolar rumo ao Destino...")
                self.provider.schedule_timer("r_fly_to_dest", now + 2.0)

            # Recebe ACK do Destino
            elif pkt.packet_type == PacketType.ACK.value and not any(p.packet_id == pkt.packet_id for p in self.buffer):
                pkt.hop_count += 1
                self.buffer = [pkt]
                self.set_node_color(self.COLOR_CARRY_ACK)
                self.set_tracked_variable("Estado", "ACK Coletado no Destino! Loiter (2.0s)")
                self.set_tracked_variable("Buffer", pkt.packet_id)
                self.log("Mula R coletou ACK do Destino! Aguardando Loiter de 2.0s antes de retornar ao Rendezvous...")
                self.provider.schedule_timer("r_return_to_rendezvous", now + 2.0)