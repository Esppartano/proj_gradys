from typing import Dict, Optional
from base_protocol import BaseFANETProtocol, METRICS
from messages import Packet, PacketType
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import Position


class FloodingProtocol(BaseFANETProtocol):
    """
    Protocolo de Inundação Controlada (Controlled Flooding) baseado em Lim & Kim (2001).
    Avaliado em topologia em malha multissalto com ramificações (Rotas Norte e Sul).
    Demonstra a difusão cega em todos os caminhos disponíveis, supressão de duplicatas
    (seen_packets), corte formal por TTL e o overhead de retransmissões redundantes
    (broadcast storm) em comparação ao GeoCast e DTN.
    """

    # Paleta de Cores RGB (Three.js 0-255)
    COLOR_BASE_IDLE = (30, 144, 255)        # Azul vibrante (Base)
    COLOR_BASE_SUCCESS = (0, 230, 115)      # Verde esmeralda (Concluído)
    COLOR_ROUTER_IDLE = (180, 180, 180)     # Cinza metálico (Roteador em espera)
    COLOR_ROUTER_DATA = (255, 140, 0)       # Laranja vibrante (Inundando Dados)
    COLOR_ROUTER_EXTRANEOUS = (220, 100, 0) # Laranja escuro (Ramo redundante/inútil)
    COLOR_ROUTER_ACK = (0, 210, 255)        # Ciano vibrante (Inundando ACK)
    COLOR_TARGET_WAITING = (220, 20, 60)    # Vermelho carmesim (Alvo aguardando)
    COLOR_TARGET_RECEIVED = (50, 205, 50)   # Verde vivo (Alvo recebeu pacote)
    COLOR_FINISHED = (50, 205, 50)          # Verde vivo

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

        # Nó 1: Drone Relé Rota Norte (Em Patrulha)
        elif my_id == 1:
            self.patrol_a = (20.0, 15.0, 15.0)
            self.patrol_b = (28.0, 15.0, 18.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_ROUTER_IDLE)
            self.set_tracked_variable("Papel", "Drone Relé Norte (1)")
            self.set_tracked_variable("Estado", "Patrulha Ativa Norte")

        # Nó 2: Drone Relé Rota Sul (Em Patrulha)
        elif my_id == 2:
            self.patrol_a = (20.0, -15.0, 15.0)
            self.patrol_b = (28.0, -15.0, 12.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_ROUTER_IDLE)
            self.set_tracked_variable("Papel", "Drone Relé Sul (2)")
            self.set_tracked_variable("Estado", "Patrulha Ativa Sul")

        # Nó 3: Drone Periférico Sul (Ramo Extrâneo em Patrulha)
        elif my_id == 3:
            self.patrol_a = (50.0, -25.0, 15.0)
            self.patrol_b = (58.0, -25.0, 18.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_ROUTER_IDLE)
            self.set_tracked_variable("Papel", "Drone Periférico Sul (3)")
            self.set_tracked_variable("Estado", "Patrulha Ramo Cego")

        # Nó 4: Drone Alvo Nordeste (Em Patrulha na Target Zone)
        elif my_id == 4:
            self.patrol_a = (50.0, 25.0, 15.0)
            self.patrol_b = (58.0, 25.0, 12.0)
            self.heading_to_b = True
            self.set_speed(8.0)
            self.fly_to(*self.patrol_b)
            self.set_node_color(self.COLOR_TARGET_WAITING)
            self.set_tracked_variable("Papel", "Drone Alvo Nordeste (4)")
            self.set_tracked_variable("Estado", "Patrulha na Target Zone")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        super().handle_telemetry(telemetry)
        if hasattr(self, "patrol_a") and hasattr(self, "patrol_b"):
            if self.heading_to_b and self.has_reached(self.patrol_b, tolerance=1.5):
                self.heading_to_b = False
                self.fly_to(*self.patrol_a)
            elif not self.heading_to_b and self.has_reached(self.patrol_a, tolerance=1.5):
                self.heading_to_b = True
                self.fly_to(*self.patrol_b)

    def handle_timer(self, timer: str) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        # ----------------- BASE (Nó 0) -----------------
        if timer == "tower_send" and my_id == 0:
            pkt = Packet(
                packet_id="FLOOD_01",
                packet_type=PacketType.DATA.value,
                source=0,
                destination=4,
                content="ORDEM_FLOODING",
                ttl=4,
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_tracked_variable("Estado", "Pacote disparado em broadcast")
            self.log(f"Base: disparou '{pkt.packet_id}' em broadcast para a malha (TTL={pkt.ttl}, Destino={pkt.destination})")
            self.send_broadcast(pkt.serialize())

        # ----------------- ALVO (Nó 4) DISPARO DE ACK -----------------
        elif timer == "send_ack" and my_id == 4:
            orig_time = getattr(self, "orig_data_creation_time", now)
            ack = Packet(
                packet_id="ACK_FLOOD_01",
                packet_type=PacketType.ACK.value,
                source=4,
                destination=0,
                content="ACK_OK_FLOODING",
                ttl=4,
                creation_time=orig_time,
                hop_count=0
            )
            self.seen_packets.add(ack.packet_id)
            METRICS.ack_sent += 1
            self.set_tracked_variable("Estado", "Inundando ACK de confirmação")
            self.log(f"Alvo 4: disparou '{ack.packet_id}' em broadcast reverso!")
            self.send_broadcast(ack.serialize())

        # ----------------- RETRANSMISSÃO CADENCIADA NOS RELÉS -----------------
        elif timer.startswith("fwd_"):
            pkt_id = timer.split("fwd_")[1]
            if pkt_id in self.pending_forward:
                fwd_pkt = self.pending_forward.pop(pkt_id)
                self.send_broadcast(fwd_pkt.serialize())

                if my_id == 3:
                    self.log(f"Flooding: Nó 3 retransmitiu '{pkt_id}' no ramo Sul (inútil para o Alvo Norte - Extraneous Broadcast)!")
                else:
                    self.log(f"Flooding: Nó {my_id} retransmitiu '{pkt_id}' (TTL={fwd_pkt.ttl}, Salto={fwd_pkt.hop_count})")

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
        # CASO 1: Pacote endereçado a este nó (Destinatário Final)
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
                    self.log(f"FLOODING SUCESSO: Alvo 4 recebeu '{pkt.content}' em {METRICS.delivery_latency:.2f}s (Saltos: {METRICS.hops})!")

                    # Agenda difusão do ACK após 1.0s para acompanhamento visual nítido
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
                    self.log(f"FLOODING SUCESSO TOTAL: Base recebeu ACK! (RTT={METRICS.round_trip_time:.2f}s, Saltos={pkt.hop_count + 1})")

                    finish_pkt = Packet(
                        packet_id="FIN_FLOOD",
                        packet_type="FINISH",
                        source=0,
                        destination=-1,
                        content="END_OF_MISSION"
                    )
                    self.send_broadcast(finish_pkt.serialize())
            return

        # -------------------------------------------------------------
        # CASO 2: Nó intermediário repassador (Controlled Flooding)
        # -------------------------------------------------------------
        # 1. Supressão de duplicatas (Lim & Kim 2001)
        if pkt.packet_id in self.seen_packets:
            self.log(f"Flooding: Nó {my_id} DESCARTOU duplicata de '{pkt.packet_id}' (Loop suprimido com sucesso).")
            return

        self.seen_packets.add(pkt.packet_id)
        pkt.ttl -= 1
        pkt.hop_count += 1

        # 2. Descarte formal quando TTL expira
        if pkt.ttl <= 0:
            self.log(f"Flooding: Nó {my_id} DESCARTOU '{pkt.packet_id}' (TTL expirado = 0).")
            return

        # 3. Armazena para retransmissão cadenciada (1.0s para visualização fluida)
        self.pending_forward[pkt.packet_id] = pkt
        self.provider.schedule_timer(f"fwd_{pkt.packet_id}", now + 1.0)

        if pkt.packet_type == PacketType.ACK.value:
            self.set_node_color(self.COLOR_ROUTER_ACK)
            self.set_tracked_variable("Estado", f"Inundando ACK de Volta (TTL={pkt.ttl})")
        else:
            color = self.COLOR_ROUTER_EXTRANEOUS if my_id == 3 else self.COLOR_ROUTER_DATA
            self.set_node_color(color)
            self.set_tracked_variable("Estado", f"Inundando Dados (TTL={pkt.ttl}, Salto={pkt.hop_count})")