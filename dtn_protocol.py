from typing import Optional
from base_protocol import BaseFANETProtocol, METRICS
from messages import Packet, PacketType
from gradysim.protocol.messages.telemetry import Telemetry
from gradysim.protocol.position import Position


class DTNProtocol(BaseFANETProtocol):
    """
    Protocolo Delay Tolerant Network (DTN) clássico baseado em Store-Carry-Forward com 1 Mula Móvel.
    Navegação 100% reativa baseada em telemetria, tempo de permanência (Loiter/Hover) para handshakes
    visíveis e cores RGB nítidas (0-255) integradas ao visualizador 3D do GrADyS-SIM.
    """

    WAYPOINT_TARGET: Position = (115.0, 0.0, 15.0)
    WAYPOINT_BASE: Position = (10.0, 0.0, 15.0)

    # Cores RGB vibrantes (escala 0-255 para Three.js / Web Visualizer)
    COLOR_BASE_IDLE = (30, 144, 255)       # Azul vibrante (DodgerBlue)
    COLOR_BASE_SUCCESS = (0, 230, 115)     # Verde esmeralda brilhante
    COLOR_MULE_IDLE = (180, 180, 180)      # Cinza metálico neutro
    COLOR_MULE_CARRY_DATA = (255, 140, 0)  # Laranja brilhante
    COLOR_MULE_LOITER = (255, 215, 0)      # Dourado/Amarelo (Hover/Handshake)
    COLOR_MULE_CARRY_ACK = (0, 210, 255)   # Ciano vibrante
    COLOR_MULE_SUCCESS = (50, 205, 50)     # Verde vivo
    COLOR_TARGET_WAITING = (220, 20, 60)   # Vermelho carmesim
    COLOR_TARGET_RECEIVED = (50, 205, 50)  # Verde vivo

    def __init__(self):
        super().__init__()
        self.state: str = "IDLE"

    def initialize(self) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        self.show_node_id(True)
        self.resize_all_nodes(2.5)

        # Nó 0: Estação Base
        if my_id == 0:
            self.set_node_color(self.COLOR_BASE_IDLE)
            self.set_tracked_variable("Papel", "Estação Base (0)")
            self.set_tracked_variable("Estado", "Aguardando início (3s)")
            # Inicia após 3.0s para permitir que o navegador abra e conecte o WebSocket
            self.provider.schedule_timer("tower_send", now + 3.0)

        # Nó 1: Mula Móvel
        elif my_id == 1:
            self.state = "IDLE"
            self.set_node_color(self.COLOR_MULE_IDLE)
            self.set_tracked_variable("Papel", "Mula Móvel (1)")
            self.set_tracked_variable("Estado", "Pronta na Base (Aguardando ordem)")

        # Nó 2: Alvo Isolado
        elif my_id == 2:
            self.set_node_color(self.COLOR_TARGET_WAITING)
            self.set_tracked_variable("Papel", "Alvo Isolado (2)")
            self.set_tracked_variable("Estado", "Aguardando contato DTN")

    def handle_telemetry(self, telemetry: Telemetry) -> None:
        super().handle_telemetry(telemetry)
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        if my_id == 1 and not self.mission_completed:
            # 1. Chegada da Mula ao Alvo Remoto
            if self.state == "CARRYING_TO_TARGET" and self.has_reached(self.WAYPOINT_TARGET, tolerance=3.0):
                self.state = "AT_TARGET_LOITER"
                self.set_node_color(self.COLOR_MULE_LOITER)
                self.set_tracked_variable("Estado", "No Alvo: Handshake / Loiter (2.5s)")
                self.log("Mula chegou ao Alvo remoto (x=115). Iniciando Loiter de 2.5s para descarregar comando...")
                for pkt in list(self.buffer):
                    self.send_broadcast(pkt.serialize())

            # 2. Retorno da Mula à Estação Base
            elif self.state == "CARRYING_TO_BASE" and self.has_reached(self.WAYPOINT_BASE, tolerance=3.0):
                self.state = "AT_BASE_FINAL"
                self.set_node_color(self.COLOR_MULE_SUCCESS)
                self.set_tracked_variable("Estado", "Na Base: Entregando ACK Final")
                self.log("Mula pousou na Base (x=10). Descarregando ACK final com sucesso...")
                for pkt in list(self.buffer):
                    self.send_broadcast(pkt.serialize())

    def handle_timer(self, timer: str) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        # ----------------- BASE (Nó 0) -----------------
        if timer == "tower_send" and my_id == 0:
            pkt = Packet(
                packet_id="CMD_01",
                packet_type=PacketType.DATA.value,
                source=0,
                destination=2,
                content="ORDEM_DE_MISSAO",
                ttl=10,
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_tracked_variable("Estado", "Comando emitido à Mula")
            self.log(f"Base emitiu pacote '{pkt.packet_id}' para transporte da Mula.")
            self.send_broadcast(pkt.serialize())

        # ----------------- MULA (Nó 1) -----------------
        elif timer == "fly_back_to_base" and my_id == 1:
            self.state = "CARRYING_TO_BASE"
            self.set_node_color(self.COLOR_MULE_CARRY_ACK)
            self.set_tracked_variable("Estado", "Retornando com ACK -> Base")
            self.log("Loiter no Alvo encerrado. Mula decolando em voo de retorno à Base (x=10)...")
            self.fly_to(*self.WAYPOINT_BASE)

    def handle_packet(self, message: str) -> None:
        pkt = Packet.deserialize(message)
        if pkt is None:
            return

        my_id = self.provider.get_id()
        now = self.provider.current_time()

        # -------------------------------------------------------------
        # CASO 1: Pacote endereçado a este nó
        # -------------------------------------------------------------
        if pkt.destination == my_id:
            if pkt.packet_id not in self.seen_packets:
                self.seen_packets.add(pkt.packet_id)

                # Nó 2 (Alvo Isolado) recebe a ordem
                if pkt.packet_type == PacketType.DATA.value and my_id == 2:
                    METRICS.data_delivered += 1
                    METRICS.delivery_latency = now - pkt.creation_time
                    METRICS.hops = pkt.hop_count + 1
                    self.set_node_color(self.COLOR_TARGET_RECEIVED)
                    self.set_tracked_variable("Estado", f"Dado recebido ({METRICS.delivery_latency:.2f}s)")
                    self.log(f"DTN SUCESSO: Alvo recebeu '{pkt.content}' em {METRICS.delivery_latency:.2f}s!")

                    # Emite imediatamente o ACK de confirmação
                    ack = Packet(
                        packet_id="ACK_01",
                        packet_type=PacketType.ACK.value,
                        source=2,
                        destination=0,
                        content="ACK_MISSAO_CONFIRMADA",
                        ttl=10,
                        creation_time=now,
                        hop_count=0
                    )
                    self.seen_packets.add(ack.packet_id)
                    METRICS.ack_sent += 1
                    self.log("Drone Alvo emitiu ACK para a Mula levar à Base.")
                    self.send_broadcast(ack.serialize())

                # Nó 0 (Base) recebe o ACK de volta
                elif pkt.packet_type == PacketType.ACK.value and my_id == 0:
                    METRICS.ack_delivered += 1
                    METRICS.round_trip_time = now - pkt.creation_time
                    METRICS.mission_success = True
                    self.mission_completed = True
                    self.set_node_color(self.COLOR_BASE_SUCCESS)
                    self.set_tracked_variable("Estado", f"Sucesso Total (RTT={METRICS.round_trip_time:.2f}s)")
                    self.log(f"DTN SUCESSO TOTAL: ACK recebido na Base! (RTT={METRICS.round_trip_time:.2f}s, Saltos={pkt.hop_count + 1})")
            return

        # -------------------------------------------------------------
        # CASO 2: Mula Móvel (Nó 1) atuando como Store-Carry-Forward
        # -------------------------------------------------------------
        if my_id == 1 and not self.mission_completed:
            # 1. Armazena o comando da Base e voa rumo ao Alvo
            if pkt.packet_type == PacketType.DATA.value:
                if not any(p.packet_id == pkt.packet_id for p in self.buffer):
                    pkt.hop_count += 1
                    self.buffer.append(pkt)
                    self.state = "CARRYING_TO_TARGET"
                    self.set_node_color(self.COLOR_MULE_CARRY_DATA)
                    self.set_tracked_variable("Estado", "Carregando Dado -> Alvo (x=115)")
                    self.set_tracked_variable("Buffer", pkt.packet_id)
                    self.log(f"STORE: Mula guardou '{pkt.packet_id}' no buffer. Voando rumo ao Alvo (x=115)...")
                    self.fly_to(*self.WAYPOINT_TARGET)

            # 2. Ao receber o ACK do Alvo no ponto de entrega, agenda o retorno após o Loiter de 2.5s
            elif pkt.packet_type == PacketType.ACK.value:
                if not any(p.packet_id == pkt.packet_id for p in self.buffer):
                    pkt.hop_count += 1
                    self.buffer = [pkt]
                    self.set_node_color(self.COLOR_MULE_CARRY_ACK)
                    self.set_tracked_variable("Estado", "ACK Coletado! Loiter no Alvo (2.5s)")
                    self.set_tracked_variable("Buffer", pkt.packet_id)
                    self.log(f"STORE: Mula coletou '{pkt.packet_id}'. Mantendo hover no Alvo antes de retornar...")
                    # Permanece em hover por 2.5s antes de iniciar a viagem de volta
                    self.provider.schedule_timer("fly_back_to_base", now + 2.5)