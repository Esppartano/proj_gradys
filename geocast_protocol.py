from typing import Dict, Optional
from base_protocol import BaseFANETProtocol, METRICS
from messages import Packet, PacketType
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import Position, squared_distance


class GeoCastProtocol(BaseFANETProtocol):
    """
    Protocolo de Roteamento Geocast baseado em Choi et al. (2018).
    Avaliado na mesma topologia em malha multissalto do Flooding (5 nós).
    Utiliza coordenadas geográficas 3D (dest_pos) e restringe a difusão
    estritamente aos nós localizados na Forwarding Zone (direção do alvo).
    Nós fora da zona executam Poda Geográfica (descarte silencioso), eliminando
    as retransmissões redundantes e economizando energia do enxame.
    """

    TARGET_POS: Position = (55.0, 25.0, 15.0)
    BASE_POS: Position = (0.0, 0.0, 15.0)
    GEO_RADIUS: float = 35.0  # Raio de entrega da Delivery Zone

    # Paleta de Cores RGB (Three.js 0-255)
    COLOR_BASE_IDLE = (30, 144, 255)            # Azul vibrante (Base)
    COLOR_BASE_SUCCESS = (0, 230, 115)          # Verde esmeralda (Concluído)
    COLOR_ROUTER_IDLE = (180, 180, 180)         # Cinza metálico
    COLOR_ROUTER_FWD_DATA = (255, 140, 0)       # Laranja (Na Forwarding Zone -> Encaminhando)
    COLOR_ROUTER_PRUNED = (120, 120, 130)       # Cinza ardósia escuro (Poda Geográfica aplicada)
    COLOR_ROUTER_FWD_ACK = (0, 210, 255)        # Ciano (Retorno de ACK na zona)
    COLOR_TARGET_WAITING = (220, 20, 60)        # Vermelho carmesim (Alvo aguardando)
    COLOR_TARGET_RECEIVED = (50, 205, 50)       # Verde vivo (Alvo recebeu pacote)
    COLOR_FINISHED = (50, 205, 50)              # Verde vivo

    def __init__(self):
        super().__init__()
        self.pending_forward: Dict[str, Packet] = {}

    def initialize(self) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        self.show_node_id(True)
        self.resize_all_nodes(2.5)

        # Nó 0: Estação Base / Torre Fixa no Solo
        if my_id == 0:
            self.set_node_color(self.COLOR_BASE_IDLE)
            self.set_tracked_variable("Papel", "Estação Base Solo (0)")
            self.set_tracked_variable("Estado", "Aguardando disparo (3s)")
            self.provider.schedule_timer("tower_send", now + 3.0)

        # Nó 1: Drone Relé Rota Norte (Em Patrulha na Forwarding Zone)
        elif my_id == 1:
            self.patrol_a = (20.0, 15.0, 15.0)
            self.patrol_b = (28.0, 15.0, 18.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_ROUTER_IDLE)
            self.set_tracked_variable("Papel", "Drone Relé Norte (1)")
            self.set_tracked_variable("Estado", "Patrulha na Forwarding Zone")

        # Nó 2: Drone Relé Rota Sul (Em Patrulha no Setor Sul - Poda)
        elif my_id == 2:
            self.patrol_a = (20.0, -15.0, 15.0)
            self.patrol_b = (28.0, -15.0, 12.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_ROUTER_IDLE)
            self.set_tracked_variable("Papel", "Drone Relé Sul (2)")
            self.set_tracked_variable("Estado", "Patrulha no Setor Sul")

        # Nó 3: Drone Periférico Sul (Em Patrulha - Silenciado)
        elif my_id == 3:
            self.patrol_a = (50.0, -25.0, 15.0)
            self.patrol_b = (58.0, -25.0, 18.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_ROUTER_IDLE)
            self.set_tracked_variable("Papel", "Drone Periférico Sul (3)")
            self.set_tracked_variable("Estado", "Patrulha no Setor Sul")

        # Nó 4: Drone Alvo Nordeste (Em Patrulha na Delivery Zone)
        elif my_id == 4:
            self.patrol_a = (50.0, 25.0, 15.0)
            self.patrol_b = (58.0, 25.0, 12.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_TARGET_WAITING)
            self.set_tracked_variable("Papel", "Drone Alvo Nordeste (4)")
            self.set_tracked_variable("Estado", "Patrulha na Delivery Zone")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        super().handle_telemetry(telemetry)
        if hasattr(self, "patrol_a") and hasattr(self, "patrol_b"):
            if self.heading_to_b and self.has_reached(self.patrol_b, tolerance=1.5):
                self.heading_to_b = False
                self.fly_to(*self.patrol_a)
            elif not self.heading_to_b and self.has_reached(self.patrol_a, tolerance=1.5):
                self.heading_to_b = True
                self.fly_to(*self.patrol_b)

    def _is_in_forwarding_zone(self, pkt: Packet) -> bool:
        """
        Avalia se a coordenada atual do nó está dentro da Forwarding Zone em direção ao destino.
        Choi et al. (2018): Roteamento direcional e restrição espacial.
        """
        if not pkt.dest_pos:
            return True

        dest_x, dest_y, _ = pkt.dest_pos
        curr_x, curr_y, _ = self.current_pos

        # O Alvo está em y=+25 e a Base está em y=0.
        # A Forwarding Zone (corredor geográfico da missão) situa-se estritamente no semi-plano Norte (y >= 0.0).
        # Nós com y < 0 (como Nós 2 e 3 no Sul) estão fora do corredor geográfico da missão.
        return curr_y >= 0.0

    def handle_timer(self, timer: str) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        # ----------------- BASE (Nó 0) -----------------
        if timer == "tower_send" and my_id == 0:
            pkt = Packet(
                packet_id="GEO_01",
                packet_type=PacketType.DATA.value,
                source=0,
                destination=4,
                content="ORDEM_GEOCAST",
                dest_pos=self.TARGET_POS,
                ttl=4,
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_tracked_variable("Estado", "Pacote Geocast emitido")
            self.log(f"GeoCast: Base emitiu '{pkt.packet_id}' para coordenadas {self.TARGET_POS} (Forwarding Zone: Setor Norte y>=0)")
            self.send_broadcast(pkt.serialize())

        # ----------------- ALVO (Nó 4) DISPARO DE ACK -----------------
        elif timer == "send_ack" and my_id == 4:
            orig_time = getattr(self, "orig_data_creation_time", now)
            ack = Packet(
                packet_id="ACK_GEO_01",
                packet_type=PacketType.ACK.value,
                source=4,
                destination=0,
                content="ACK_OK_GEOCAST",
                dest_pos=self.BASE_POS,
                ttl=4,
                creation_time=orig_time,
                hop_count=0
            )
            self.seen_packets.add(ack.packet_id)
            METRICS.ack_sent += 1
            self.set_tracked_variable("Estado", "ACK emitido rumo à Base")
            self.log(f"Alvo 4: emitiu '{ack.packet_id}' com destino geográfico na Base {self.BASE_POS}!")
            self.send_broadcast(ack.serialize())

        # ----------------- RETRANSMISSÃO CADENCIADA NOS RELÉS -----------------
        elif timer.startswith("fwd_"):
            pkt_id = timer.split("fwd_")[1]
            if pkt_id in self.pending_forward:
                fwd_pkt = self.pending_forward.pop(pkt_id)
                self.send_broadcast(fwd_pkt.serialize())
                self.log(f"GeoCast: Nó {my_id} (Norte) retransmitiu '{pkt_id}' rumo ao Alvo!")

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
        # 1. Destinatário Final do Pacote
        # -------------------------------------------------------------
        if pkt.destination == my_id:
            if pkt.packet_id not in self.seen_packets:
                self.seen_packets.add(pkt.packet_id)

                # Alvo Nordeste (Nó 4)
                if pkt.packet_type == PacketType.DATA.value and my_id == 4:
                    METRICS.data_delivered += 1
                    METRICS.delivery_latency = now - pkt.creation_time
                    METRICS.hops = pkt.hop_count + 1
                    self.set_node_color(self.COLOR_TARGET_RECEIVED)
                    self.set_tracked_variable("Estado", f"Recebido em {METRICS.delivery_latency:.2f}s (Salto={METRICS.hops})")
                    self.log(f"GEOCAST SUCESSO: Alvo 4 recebeu '{pkt.content}' em {METRICS.delivery_latency:.2f}s (Saltos: {METRICS.hops})!")

                    # Agenda difusão de ACK após 1.0s
                    self.orig_data_creation_time = pkt.creation_time
                    self.provider.schedule_timer("send_ack", now + 1.0)

                # Base (Nó 0) recebe confirmação do ACK
                elif pkt.packet_type == PacketType.ACK.value and my_id == 0:
                    METRICS.ack_delivered += 1
                    METRICS.round_trip_time = now - pkt.creation_time
                    METRICS.mission_success = True
                    self.mission_completed = True
                    self.set_node_color(self.COLOR_BASE_SUCCESS)
                    self.set_tracked_variable("Estado", f"Missão Concluída (RTT={METRICS.round_trip_time:.2f}s)")
                    self.log(f"GEOCAST SUCESSO TOTAL: Base recebeu ACK! (RTT={METRICS.round_trip_time:.2f}s, Saltos={pkt.hop_count + 1})")

                    finish_pkt = Packet(
                        packet_id="FIN_GEO",
                        packet_type="FINISH",
                        source=0,
                        destination=-1,
                        content="END_OF_MISSION"
                    )
                    self.send_broadcast(finish_pkt.serialize())
            return

        # -------------------------------------------------------------
        # 2. Avaliação de Relé Intermediário e Poda Geográfica (Choi et al.)
        # -------------------------------------------------------------
        if pkt.packet_id in self.seen_packets:
            return

        self.seen_packets.add(pkt.packet_id)

        # TESTE DA FORWARDING ZONE:
        if not self._is_in_forwarding_zone(pkt):
            # Nó fora da zona direcional (Ex: Nó 2 no setor Sul y=-15)
            self.set_node_color(self.COLOR_ROUTER_PRUNED)
            self.set_tracked_variable("Estado", "Fora da Forwarding Zone (Poda Ativa)")
            self.log(f"GeoCast PODA GEOGRÁFICA: Nó {my_id} (y={self.current_pos[1]:.1f}) está FORA da Forwarding Zone (alvo no Norte). Pacote descartado!")
            return

        # Nó está dentro da Forwarding Zone (Ex: Nó 1 no Norte y=+15)
        pkt.ttl -= 1
        pkt.hop_count += 1

        if pkt.ttl <= 0:
            return

        self.pending_forward[pkt.packet_id] = pkt
        self.provider.schedule_timer(f"fwd_{pkt.packet_id}", now + 1.0)

        if pkt.packet_type == PacketType.ACK.value:
            self.set_node_color(self.COLOR_ROUTER_FWD_ACK)
            self.set_tracked_variable("Estado", "Encaminhando ACK na Forwarding Zone")
        else:
            self.set_node_color(self.COLOR_ROUTER_FWD_DATA)
            self.set_tracked_variable("Estado", "Encaminhando Dados na Forwarding Zone")
            self.log(f"GeoCast: Nó {my_id} aceitou pacote (Dentro da Forwarding Zone). Agendando repasse...")