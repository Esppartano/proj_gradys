import math
from typing import Dict, List, Optional, Set, Tuple
from base_protocol import BaseFANETProtocol, METRICS
from messages import Packet, PacketType
from gradysim.protocol.position import Position


class SwarmCoreProtocol(BaseFANETProtocol):
    """
    Protocolo Swarm Core com Formação em V e Torre Terrestre (GrADyS / PUC-Rio).

    Estrutura da Rede (14 nós):
      - Nó 0: Torre Terrestre (Estação Base fixa no solo)
      - Nós 1 a 9: Núcleo do Enxame (Swarm Core em Formação V)
          * Nó 1: Ápice / Líder da formação (Root da Spanning Tree)
          * Nós 2, 3, 4, 5: Asa Esquerda (C2, C3, C4, C5)
          * Nós 6, 7, 8, 9: Asa Direita (C6, C7, C8, C9)
      - Nós 10 a 13: Satélites Periféricos (S1, S2, S3, S4)
          * Orbitam ao redor do Swarm Core
          * Acoplam temporariamente (T segundos) em tandem com nós do Core
          * Enviam mensagens assíncronas entre satélites e para a Torre

    Dinâmica de Enxame Implementada:
      - Rotação suave da formação em V em torno do ponto central.
      - Revezamento de nós na formação: Nó C4 sai da formação para ronda externa;
        o nó C5 e a asa se rearranjam automaticamente (FF Control) para manter
        o padrão em V contínuo e a Spanning Tree conexa.
      - Posteriormente, o nó retorna/reentra no Core e a geometria se restabelece.
      - Cadência visual deliberada (0.8s por salto) para acompanhamento nítido no 3D.
    """

    # Centro de Rotação da Formação em V (Centro de Massa)
    CENTER_X: float = 25.0
    CENTER_Y: float = 0.0
    CORE_ALTITUDE: float = 15.0
    TOWER_ALTITUDE: float = 5.0
    SATELLITE_ALTITUDE: float = 17.5
    ROTATION_OMEGA: float = 0.2856  # rad/s (conclui 1 volta completa de 360° em 22.0 segundos)
    STEP_INTERVAL: float = 0.4      # segundos (atualização contínua e suave da trajetória)
    HOP_DELAY: float = 0.65         # segundos por salto na Spanning Tree para clareza visual

    # Coordenadas da Formação em V Afunilada e Reta (Leader-Follower ao longo da Órbita):
    # u: raio da órbita em relação ao Nó Central (Líder C1 orbita a R=34.0m; asa esquerda R>34m; asa direita R<34m)
    # v: distância longitudinal atrás do Líder C1 ao longo do vetor velocidade tangencial
    LOCAL_V_COORDS: Dict[int, Tuple[float, float]] = {
        1: (34.0, 0.0),   # C1: Ápice Líder da formação (orbita o nó central a R=34m)
        2: (36.0, 5.5),   # C2: Asa Esquerda Salto 1 (seguidor externo)
        3: (38.0, 11.0),  # C3: Asa Esquerda Salto 2
        4: (40.0, 16.5),  # C4: Asa Esquerda Salto 3 (sai temporariamente para ronda externa)
        5: (42.0, 22.0),  # C5: Asa Esquerda Salto 4 / Hub S1 (FF Control: cobre vaga de C4)
        6: (32.0, 5.5),   # C6: Asa Direita Salto 1 (seguidor interno)
        7: (30.0, 11.0),  # C7: Asa Direita Salto 2
        8: (28.0, 16.5),  # C8: Asa Direita Salto 3
        9: (26.0, 22.0),  # C9: Asa Direita Salto 4 / Hub S3
    }

    # Paleta de Cores RGB de Alto Contraste (Three.js 0-255)
    COLOR_TOWER = (20, 60, 220)          # Azul Royal Profundo (Torre Terrestre Solo)
    COLOR_APEX = (160, 32, 240)          # Roxo Imperial Neon (Ápice / Líder do V)
    COLOR_CORE_WING = (30, 144, 255)     # Azul Claro Vivo (Drones das Asas do V)
    COLOR_CORE_ADJUSTED = (0, 190, 255)  # Turquesa (Nó rearranjado por FF Control)
    COLOR_SATELLITE_ORBIT = (255, 140, 0)# Laranja Solar (Satélite em Órbita Periférica)
    COLOR_TANDEM = (255, 230, 0)         # Amarelo Ouro Neon (Acoplado em Voo Tandem)
    COLOR_TRANSMITTING = (255, 120, 0)   # Laranja Brilhante (Transmitindo Pacote)
    COLOR_FWD_ROUTING = (0, 255, 255)    # Ciano Elétrico Puro (Recebendo/Encaminhando)
    COLOR_DATA_RECV = (0, 255, 80)       # Verde Limão Neon (Dado Entregue com Sucesso)
    COLOR_MISSION_COMPLETE = (0, 230, 115) # Verde Esmeralda (Missão Concluída)

    def __init__(self):
        super().__init__()
        self.role: str = "UNKNOWN"
        self.is_tower: bool = False
        self.is_core: bool = False
        self.is_satellite: bool = False
        self.is_exited: bool = False
        self.is_rearranged: bool = False
        self.is_tandem: bool = False
        self.tandem_target_id: Optional[int] = None
        self.orbit_phase: float = 0.0
        self.orbit_omega: float = 0.10
        self.orbit_radius: float = 48.0
        self.pending_forward: Dict[str, Packet] = {}
        self.revolving_angle: float = 0.0

    def initialize(self) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        self.show_node_id(True)
        self.resize_all_nodes(2.5)

        # 1. Torre Terrestre (Nó 0)
        if my_id == 0:
            self.role = "TOWER"
            self.is_tower = True
            self.set_node_color(self.COLOR_TOWER)
            self.set_tracked_variable("Papel", "Torre Terrestre / Estação Base (0)")
            self.set_tracked_variable("Estado", "Aguardando Janela de Disparo (2.0s)")
            self.set_tracked_variable("Tipo", "Estação de Solo Fixa")
            self.provider.schedule_timer("tower_send_mission", now + 2.0)

        # 2. Nós do Swarm Core em Formação V (Nós 1 a 9)
        elif 1 <= my_id <= 9:
            self.role = "CORE"
            self.is_core = True
            if my_id == 1:
                self.set_node_color(self.COLOR_APEX)
                self.set_tracked_variable("Papel", "Core Ápice Líder (C1)")
                self.set_tracked_variable("Estado", "Formação V Aguda / Rotação no CM")
                self.set_tracked_variable("Topologia", "Root da Spanning Tree")
            elif 2 <= my_id <= 5:
                self.set_node_color(self.COLOR_CORE_WING)
                self.set_tracked_variable("Papel", f"Core Asa Esquerda (C{my_id})")
                self.set_tracked_variable("Estado", "Formação V Aguda")
                self.set_tracked_variable("Topologia", f"Spanning Tree Salto {my_id - 1}")
            else:  # 6 <= my_id <= 9
                self.set_node_color(self.COLOR_CORE_WING)
                self.set_tracked_variable("Papel", f"Core Asa Direita (C{my_id})")
                self.set_tracked_variable("Estado", "Formação V Aguda")
                self.set_tracked_variable("Topologia", f"Spanning Tree Salto {my_id - 5}")

            # Inicia rotação no Centro de Massa
            self.provider.schedule_timer("step_rotation", now + 1.0)

            # Programação dos eventos de dinâmica de enxame:
            # - Em t = 12.0s: C4 sai da formação para ronda externa de patrulha
            if my_id == 4:
                self.provider.schedule_timer("core_exit_formation", now + 12.0)
            # - Em t = 12.5s: C5 rearranja sua posição cobrindo a vaga de C4 (FF Control)
            if my_id == 5:
                self.provider.schedule_timer("core_rearrange_wing", now + 12.5)

        # 3. Satélites Periféricos (Nós 10 a 13)
        elif 10 <= my_id <= 13:
            self.role = "SATELLITE"
            self.is_satellite = True
            sat_names = {10: "S1 (Sudeste)", 11: "S2 (Norte)", 12: "S3 (Nordeste)", 13: "S4 (Oeste)"}
            self.set_tracked_variable("Papel", f"Satélite {sat_names.get(my_id)}")

            phases = {
                10: -0.48,   # S1: Sudeste (inicia conectado a C5 em tandem por T=7.5s)
                11: 1.695,   # S2: Norte (órbita periférica independente)
                12: 1.30,    # S3: Nordeste (órbita periférica, acopla a C9 em t=10.0s)
                13: 2.78     # S4: Oeste (órbita periférica independente)
            }
            self.orbit_phase = phases.get(my_id, 0.0)
            self.orbit_omega = 0.10
            self.orbit_radius = 48.0

            if my_id == 10:
                self.is_tandem = True
                self.tandem_target_id = 5
                self.set_node_color(self.COLOR_TANDEM)
                self.set_tracked_variable("Estado", "Voo Tandem Acoplado com Hub C5 (T=7.5s)")
                self.log("ACOPLAMENTO TANDEM: Satélite S1 conectado ao Hub C5 em movimento tandem!")
                self.provider.schedule_timer("undock_tandem_s1", now + 7.5)
            elif my_id == 12:
                self.is_tandem = False
                self.tandem_target_id = None
                self.set_node_color(self.COLOR_SATELLITE_ORBIT)
                self.set_tracked_variable("Estado", "Órbita Periférica ao redor do Core")
                self.provider.schedule_timer("dock_tandem_s3_c9", now + 10.0)
            else:
                self.is_tandem = False
                self.tandem_target_id = None
                self.set_node_color(self.COLOR_SATELLITE_ORBIT)
                self.set_tracked_variable("Estado", "Órbita Periférica ao redor do Core")

            # Inicia movimento dos satélites
            self.provider.schedule_timer("satellite_orbit_step", now + 0.1)

    # -----------------------------------------------------------------
    # Roteamento Determinístico na Árvore Geradora (Spanning Tree)
    # -----------------------------------------------------------------
    def _get_spanning_tree_next_hop(self, current: int, dest: int) -> int:
        """
        Calcula o próximo salto determinístico na Spanning Tree da Formação em V:
          Torre 0 <---> C1 (Ápice)
          Asa Esquerda: C1 <---> C2 <---> C3 <---> C4 <---> C5
          (Durante 12.5s a 22.0s, C4 sai em ronda e C5 avança cobrindo a vaga: C3 <---> C5)
          Asa Direita:  C1 <---> C6 <---> C7 <---> C8 <---> C9
          Satélites: S1 (10), S2 (11), S3 (12), S4 (13)
        """
        if current == dest:
            return current

        now = self.provider.current_time()
        is_rearranged = (12.5 <= now < 22.0)

        # 1. Rota rumo à Torre Terrestre (dest == 0)
        if dest == 0:
            if current == 1:
                return 0
            elif 2 <= current <= 5:
                if is_rearranged and current == 5:
                    return 3
                return current - 1
            elif 6 <= current <= 9:
                return 1 if current == 6 else current - 1
            elif current == 10:
                return 5
            elif current == 12:
                return 9
            elif current == 13:
                return 9

        # 2. Torre sempre entrega ao Ápice C1
        if current == 0:
            return 1

        # 3. Rota rumo ao Satélite S1 (dest == 10)
        if dest == 10:
            if current == 5:
                return 10
            if current == 1:
                return 2
            elif 2 <= current <= 4:
                if is_rearranged and current == 3:
                    return 5
                return current + 1
            elif 6 <= current <= 9:
                return 1 if current == 6 else current - 1

        # 4. Rota rumo ao Satélite S2 (dest == 11, Norte) - entregue por C1
        if dest == 11:
            if current == 1:
                return 11
            elif 2 <= current <= 5:
                if is_rearranged and current == 5:
                    return 3
                return current - 1
            elif 6 <= current <= 9:
                return 1 if current == 6 else current - 1
            elif current == 10:
                return 5
            elif current == 12:
                return 9

        # 5. Rota rumo ao Satélite S3 (dest == 12, Nordeste) - entregue por C9
        if dest == 12:
            if current == 9:
                return 12
            if current == 1:
                return 6
            elif 6 <= current <= 8:
                return current + 1
            elif 2 <= current <= 5:
                if is_rearranged and current == 5:
                    return 3
                return current - 1

        # 6. Rota rumo ao Satélite S4 (dest == 13, Oeste/Sul) - entregue por C5
        if dest == 13:
            if current == 5:
                return 13
            if current == 11:
                return 1
            if current == 1:
                return 2
            elif 2 <= current <= 4:
                if is_rearranged and current == 3:
                    return 5
                return current + 1
            elif 6 <= current <= 9:
                return 1 if current == 6 else current - 1

        return current

    # -----------------------------------------------------------------
    # Manipulador de Temporizadores e Máquina de Estados
    # -----------------------------------------------------------------
    def handle_timer(self, timer: str) -> None:
        my_id = self.provider.get_id()
        now = self.provider.current_time()

        # =============================================================
        # 1. TORRE TERRESTRE: Disparo da Missão (t = 2.0s)
        # =============================================================
        if timer == "tower_send_mission" and my_id == 0:
            pkt = Packet(
                packet_id="CMD_MISSION_01",
                packet_type=PacketType.DATA.value,
                source=0,
                destination=10,  # Envia ordem para o Satélite S1 via Ápice C1
                content="ORDEM_MISSAO_SWARM",
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_node_color(self.COLOR_TRANSMITTING)
            self.set_tracked_variable("Estado", "Comando emitido -> Ápice C1")
            self.log(f"Torre Terrestre (0): Iniciou missão! Enviando '{pkt.packet_id}' para Ápice C1...")
            self.send_unicast(pkt.serialize(), destination=1)

        # =============================================================
        # 2. CORE: Líder C1 Orbita o Nó Central e Seguidores Acompanham
        # =============================================================
        elif timer == "step_rotation" and self.is_core:
            angle = now * self.ROTATION_OMEGA
            if not self.is_exited:
                # Coordenadas locais (com suporte a rearranjo FF se C4 saiu)
                if self.is_rearranged and my_id == 5:
                    u, v = self.LOCAL_V_COORDS[4]  # C5 assumiu a vaga de C4
                else:
                    u, v = self.LOCAL_V_COORDS[my_id]

                # Cinemática Leader-Follower ao longo da órbita:
                # O Líder C1 (u=34, v=0) orbita o Nó Central (Torre) a R=34m.
                # Os outros nós seguem C1 respeitando a formação em V afunilada e reta atrás dele.
                rot_x = self.CENTER_X + u * math.cos(angle) + v * math.sin(angle)
                rot_y = self.CENTER_Y + u * math.sin(angle) - v * math.cos(angle)

                self.set_speed(14.0)
                self.fly_to(rot_x, rot_y, self.CORE_ALTITUDE)

            if now < 35.0:
                self.provider.schedule_timer("step_rotation", now + self.STEP_INTERVAL)

        # =============================================================
        # 3. REVEZAMENTO E REARRANJO DA FORMAÇÃO (FF Control)
        # =============================================================
        # Nó C4 sai da formação em V para ronda externa de patrulha (t = 12.0s)
        elif timer == "core_exit_formation" and my_id == 4:
            self.is_exited = True
            self.set_node_color(self.COLOR_SATELLITE_ORBIT)
            self.set_tracked_variable("Papel", "Core C4 (Em Ronda Externa)")
            self.set_tracked_variable("Estado", "Executando Ronda de Patrulha Externa (Altitude 22m)")
            self.set_speed(14.0)
            self.fly_to(self.CENTER_X - 35.0, self.CENTER_Y + 35.0, 22.0)
            self.log("SWARM REVEZAMENTO: Nó C4 saiu da formação em V para executar ronda externa!")
            self.provider.schedule_timer("core_ronda_pt2", now + 4.0)
            self.provider.schedule_timer("core_start_return", now + 7.0)
            self.provider.schedule_timer("core_reenter_formation", now + 10.0)

        # Nó C4 atinge o segundo ponto de patrulha (t = 16.0s)
        elif timer == "core_ronda_pt2" and my_id == 4:
            self.set_speed(14.0)
            self.fly_to(self.CENTER_X - 10.0, self.CENTER_Y + 50.0, 22.0)
            self.log("SWARM REVEZAMENTO: Nó C4 em segundo ponto de ronda externa de patrulha!")

        # Nó C4 inicia aproximação e interceptação para reentrar no slot 4 (t = 19.0s)
        elif timer == "core_start_return" and my_id == 4:
            target_angle = 22.0 * self.ROTATION_OMEGA
            u, v = self.LOCAL_V_COORDS[4]
            ret_x = self.CENTER_X + u * math.cos(target_angle) + v * math.sin(target_angle)
            ret_y = self.CENTER_Y + u * math.sin(target_angle) - v * math.cos(target_angle)
            self.set_speed(14.0)
            self.fly_to(ret_x, ret_y, self.CORE_ALTITUDE)
            self.log("SWARM REVEZAMENTO: Nó C4 iniciando aproximação para reentrar no Core!")

        # Nó C5 se rearranja para manter a geometria da asa esquerda (t = 12.5s)
        elif timer == "core_rearrange_wing" and my_id == 5:
            self.is_rearranged = True
            self.set_node_color(self.COLOR_CORE_ADJUSTED)
            self.set_tracked_variable("Papel", "Core C5 (Rearranjado por FF Control)")
            self.set_tracked_variable("Estado", "Cobriu vaga de C4 (Geometria em V Preservada)")
            self.log("FF CONTROL: Nó C5 ajustou posição no V mantendo a topologia rígida da asa esquerda!")
            self.provider.schedule_timer("core_restore_wing", now + 9.5)

        # Nó C4 reentra no Core e restaura a formação original de 9 nós (t = 22.0s)
        elif timer == "core_reenter_formation" and my_id == 4:
            self.is_exited = False
            self.set_node_color(self.COLOR_CORE_WING)
            self.set_tracked_variable("Papel", "Core Asa Esquerda (C4)")
            self.set_tracked_variable("Estado", "Reentrou no Core / Formação 100% Restaurada")
            self.log("SWARM REVEZAMENTO: Nó C4 reentrou no Swarm Core! Formação em V completa restaurada.")

        # Nó C5 retorna à ponta da asa esquerda (t = 22.0s)
        elif timer == "core_restore_wing" and my_id == 5:
            self.is_rearranged = False
            self.set_node_color(self.COLOR_CORE_WING)
            self.set_tracked_variable("Papel", "Core Asa Esquerda (C5)")
            self.set_tracked_variable("Estado", "Retornou à ponta da asa / Formação normalizada")
            self.log("FF CONTROL: Nó C5 retornou à ponta da asa após reentrada de C4!")

        # =============================================================
        # 4. SATÉLITES: Órbita Periférica e Acoplamento em Tandem
        # =============================================================
        elif timer == "satellite_orbit_step" and self.is_satellite:
            angle = now * self.ROTATION_OMEGA

            if self.is_tandem:
                # Voo em tandem: acompanha a rotação do respectivo Hub a z=17.5m
                hub_id = self.tandem_target_id
                if hub_id == 5 and (self.is_rearranged or (12.5 <= now < 22.0)):
                    hub_coords = self.LOCAL_V_COORDS[4]
                else:
                    hub_coords = self.LOCAL_V_COORDS.get(hub_id, (0.0, 0.0))

                u, v = hub_coords
                td_x = self.CENTER_X + u * math.cos(angle) + v * math.sin(angle)
                td_y = self.CENTER_Y + u * math.sin(angle) - v * math.cos(angle)
                self.set_speed(14.0)
                self.fly_to(td_x, td_y, self.SATELLITE_ALTITUDE)
            else:
                # Órbita circular suave ao redor do centro do Core (raio 48m)
                orbit_angle = self.orbit_phase + (now * self.orbit_omega)
                orb_x = self.CENTER_X + self.orbit_radius * math.cos(orbit_angle)
                orb_y = self.CENTER_Y + self.orbit_radius * math.sin(orbit_angle)
                self.set_speed(14.0)
                self.fly_to(orb_x, orb_y, self.SATELLITE_ALTITUDE)

            if now < 35.0:
                self.provider.schedule_timer("satellite_orbit_step", now + self.STEP_INTERVAL)

        # Desacoplamento de S1 do Hub C5 (t = 7.5s)
        elif timer == "undock_tandem_s1" and my_id == 10:
            self.is_tandem = False
            self.tandem_target_id = None
            angle = now * self.ROTATION_OMEGA
            u, v = self.LOCAL_V_COORDS[5]
            td_x = u * math.cos(angle) + v * math.sin(angle)
            td_y = u * math.sin(angle) - v * math.cos(angle)
            cur_angle = math.atan2(td_y, td_x)
            self.orbit_phase = cur_angle - (now * self.orbit_omega)
            self.set_node_color(self.COLOR_SATELLITE_ORBIT)
            self.set_tracked_variable("Estado", "Desacoplou de C5 / Retomou Órbita Periférica")
            self.log("DESACOPLAMENTO: Satélite S1 desacoplou de C5 e retomou órbita independente.")

        # Disparo da Mensagem S1 -> S2 via Hub C5 (t = 6.0s)
        elif timer == "send_msg_s1_to_s2" and my_id == 10:
            pkt = Packet(
                packet_id="MSG_S1_TO_S2",
                packet_type=PacketType.DATA.value,
                source=10,
                destination=11,  # Endereçado ao Satélite S2 (Norte)
                content="TELEMETRIA_S1_PARA_S2",
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_node_color(self.COLOR_TRANSMITTING)
            self.log("Swarm Core [S1 -> S2]: S1 injetou 'MSG_S1_TO_S2' no Hub C5 para entrega em S2 via Ápice C1!")
            self.send_unicast(pkt.serialize(), destination=5)

        # Acoplamento de S3 com Hub C9 (t = 10.0s)
        elif timer == "dock_tandem_s3_c9" and my_id == 12:
            self.is_tandem = True
            self.tandem_target_id = 9
            self.set_node_color(self.COLOR_TANDEM)
            self.set_tracked_variable("Estado", "Voo Tandem Acoplado com Hub C9 (T=2.5s)")
            self.log("ACOPLAMENTO TANDEM: Satélite S3 conectou-se ao Hub C9 em movimento tandem!")
            self.provider.schedule_timer("send_msg_s3_to_s2", now + 0.5)
            self.provider.schedule_timer("undock_tandem_s3", now + 2.5)

        # Desacoplamento de S3 do Hub C9 (t = 12.5s)
        elif timer == "undock_tandem_s3" and my_id == 12:
            self.is_tandem = False
            self.tandem_target_id = None
            angle = now * self.ROTATION_OMEGA
            u, v = self.LOCAL_V_COORDS[9]
            td_x = u * math.cos(angle) + v * math.sin(angle)
            td_y = u * math.sin(angle) - v * math.cos(angle)
            cur_angle = math.atan2(td_y, td_x)
            self.orbit_phase = cur_angle - (now * self.orbit_omega)
            self.set_node_color(self.COLOR_SATELLITE_ORBIT)
            self.set_tracked_variable("Estado", "Desacoplou de C9 / Retomou Órbita Periférica")
            self.log("DESACOPLAMENTO: Satélite S3 desacoplou de C9 e retomou órbita independente.")

        # Disparo da Mensagem S3 -> S2 via Hub C9 (t = 10.5s)
        elif timer == "send_msg_s3_to_s2" and my_id == 12:
            pkt = Packet(
                packet_id="MSG_S3_TO_S2",
                packet_type=PacketType.DATA.value,
                source=12,
                destination=11,  # Endereçado ao Satélite S2 (Norte)
                content="DADOS_SENSOR_S3_PARA_S2",
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_node_color(self.COLOR_TRANSMITTING)
            self.log("Swarm Core [S3 -> S2]: S3 injetou 'MSG_S3_TO_S2' no Hub C9 para entrega em S2 via Ápice C1!")
            self.send_unicast(pkt.serialize(), destination=9)

        # Disparo da Mensagem S2 -> S4 via Ápice C1 (t = 14.5s)
        elif timer == "send_msg_s2_to_s4" and my_id == 11:
            pkt = Packet(
                packet_id="MSG_S2_TO_S4",
                packet_type=PacketType.DATA.value,
                source=11,
                destination=13,  # Endereçado ao Satélite S4 (Sul)
                content="ORDEM_RECONFIG_S2_PARA_S4",
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(pkt.packet_id)
            METRICS.data_sent += 1
            self.set_node_color(self.COLOR_TRANSMITTING)
            self.log("Swarm Core [S2 -> S4]: S2 disparou 'MSG_S2_TO_S4' via Ápice C1 cruzando a formação em direção a S4!")
            self.send_unicast(pkt.serialize(), destination=1)

        # Disparo do Relatório Final para a Torre Terrestre (t = 23.0s)
        elif timer == "send_report_to_tower" and my_id == 13:
            report_pkt = Packet(
                packet_id="REPORT_TO_TOWER",
                packet_type=PacketType.DATA.value,
                source=13,
                destination=0,
                content="RELATORIO_FINAL_CONSOLIDADO",
                creation_time=now,
                hop_count=0
            )
            self.seen_packets.add(report_pkt.packet_id)
            METRICS.data_sent += 1
            self.set_node_color(self.COLOR_TRANSMITTING)
            self.log("Satélite S4: Enviando relatório consolidado para a Torre Terrestre (0) via Hub C9 e Ápice C1...")
            self.send_unicast(report_pkt.serialize(), destination=9)

        # =============================================================
        # 5. RETRANSMISSÃO CADENCIADA PELA SPANNING TREE (HOP_DELAY por salto)
        # =============================================================
        elif timer.startswith("fwd:"):
            _, pkt_id = timer.split(":")
            if pkt_id in self.pending_forward:
                fwd_pkt = self.pending_forward.pop(pkt_id)
                next_hop = getattr(fwd_pkt, "next_hop_target", None)
                if next_hop is not None:
                    self.send_unicast(fwd_pkt.serialize(), next_hop)
                    node_label = f"Torre 0" if my_id == 0 else (f"C{my_id}" if my_id <= 9 else f"S{my_id - 9}")
                    target_label = f"Torre 0" if next_hop == 0 else (f"C{next_hop}" if next_hop <= 9 else f"S{next_hop - 9}")
                    dest_label = f"Torre 0" if fwd_pkt.destination == 0 else (f"C{fwd_pkt.destination}" if fwd_pkt.destination <= 9 else f"S{fwd_pkt.destination - 9}")
                    self.log(f"[{node_label} -> {target_label}] Repassou '{pkt_id}' via Spanning Tree (Destino Final: {dest_label})")

    # -----------------------------------------------------------------
    # Manipulador de Pacotes Recebidos
    # -----------------------------------------------------------------
    def handle_packet(self, message: str) -> None:
        pkt = Packet.deserialize(message)
        if pkt is None:
            return

        my_id = self.provider.get_id()
        now = self.provider.current_time()

        if pkt.packet_type == "FINISH":
            self.mission_completed = True
            self.set_node_color(self.COLOR_MISSION_COMPLETE)
            self.set_tracked_variable("Estado", "Missão Concluída com Sucesso Total")
            return

        # -------------------------------------------------------------
        # A. DESTINATÁRIO FINAL ALCANÇADO
        # -------------------------------------------------------------
        if pkt.destination == my_id:
            if pkt.packet_id not in self.seen_packets:
                self.seen_packets.add(pkt.packet_id)

                # 1. Satélite S1 (Nó 10) recebe ordem inicial da Torre
                if my_id == 10 and pkt.packet_id == "CMD_MISSION_01":
                    METRICS.data_delivered += 1
                    lat = now - pkt.creation_time
                    METRICS.delivery_latency = lat
                    self.set_node_color(self.COLOR_DATA_RECV)
                    self.set_tracked_variable("Estado", "Ordem da Torre Recebida! Agendando envio para S2...")
                    self.log(f"Satélite S1: Recebeu ordem da Torre Terrestre (0) em {lat:.2f}s! Agendando envio para S2...")
                    self.provider.schedule_timer("send_msg_s1_to_s2", now + 0.75)
                    return

                # 2. Satélite S2 (Nó 11) recebe mensagem de S1
                elif my_id == 11 and pkt.packet_id == "MSG_S1_TO_S2":
                    METRICS.data_delivered += 1
                    lat = now - pkt.creation_time
                    METRICS.delivery_latency = lat
                    METRICS.hops = pkt.hop_count + 1
                    self.set_node_color(self.COLOR_DATA_RECV)
                    self.set_tracked_variable("Estado", f"Recebeu MSG de S1 em {lat:.2f}s (Saltos: {METRICS.hops})")
                    self.log(f"SWARM CORE SUCESSO [S1 -> S2]: Satélite S2 recebeu '{pkt.content}' de S1 via Ápice C1 em {lat:.2f}s (Saltos: {METRICS.hops})!")
                    return

                # 3. Satélite S2 (Nó 11) recebe mensagem de S3
                elif my_id == 11 and pkt.packet_id == "MSG_S3_TO_S2":
                    METRICS.data_delivered += 1
                    lat = now - pkt.creation_time
                    METRICS.delivery_latency = lat
                    METRICS.hops = pkt.hop_count + 1
                    self.set_node_color(self.COLOR_DATA_RECV)
                    self.set_tracked_variable("Estado", f"Recebeu MSG de S3 em {lat:.2f}s (Saltos: {METRICS.hops})")
                    self.log(f"SWARM CORE SUCESSO [S3 -> S2]: Satélite S2 recebeu '{pkt.content}' de S3 via Ápice C1 em {lat:.2f}s (Saltos: {METRICS.hops})!")
                    # Agenda envio da mensagem de S2 para S4
                    self.provider.schedule_timer("send_msg_s2_to_s4", now + 0.75)
                    return

                # 4. Satélite S4 (Nó 13) recebe mensagem de S2
                elif my_id == 13 and pkt.packet_id == "MSG_S2_TO_S4":
                    METRICS.data_delivered += 1
                    lat = now - pkt.creation_time
                    METRICS.delivery_latency = lat
                    METRICS.hops = pkt.hop_count + 1
                    self.set_node_color(self.COLOR_DATA_RECV)
                    self.set_tracked_variable("Estado", f"Recebeu MSG de S2 em {lat:.2f}s (Saltos: {METRICS.hops})")
                    self.log(f"SWARM CORE SUCESSO [S2 -> S4]: Satélite S4 recebeu '{pkt.content}' de S2 via Hub C5 em {lat:.2f}s (Saltos: {METRICS.hops})!")
                    # Agenda envio do relatório final para a Torre após restauração completa da formação (t = 23.0s)
                    delay_report = max(0.5, 23.0 - now)
                    self.provider.schedule_timer("send_report_to_tower", now + delay_report)
                    return

                # 5. Torre Terrestre (Nó 0) recebe relatório final da missão
                elif my_id == 0:
                    METRICS.data_delivered += 1
                    METRICS.mission_success = True
                    self.mission_completed = True
                    rtt = now - 2.0  # tempo decorrido desde o início da missão em t = 2.0s
                    METRICS.round_trip_time = rtt
                    self.set_node_color(self.COLOR_MISSION_COMPLETE)
                    self.set_tracked_variable("Estado", f"Missão 100% Concluída (RTT={rtt:.2f}s)")
                    self.log(f"TORRE TERRESTRE (0): RELATÓRIO RECEBIDO COM SUCESSO TOTAL! Missão Swarm Core Concluída com 100% de Entrega (RTT={rtt:.2f}s)!")

                    # Emite pacote de finalização para toda a rede
                    fin = Packet(
                        packet_id="FIN_SWARM",
                        packet_type="FINISH",
                        source=0,
                        destination=-1,
                        content="END_OF_MISSION"
                    )
                    self.send_broadcast(fin.serialize())
            return

        # -------------------------------------------------------------
        # B. ENCAMINHAMENTO DETERMINÍSTICO NA SPANNING TREE (Relé)
        # -------------------------------------------------------------
        if pkt.packet_id in self.seen_packets:
            return
        self.seen_packets.add(pkt.packet_id)

        pkt.ttl -= 1
        pkt.hop_count += 1
        if pkt.ttl <= 0:
            return

        # Calcula o próximo salto determinístico
        next_hop = self._get_spanning_tree_next_hop(my_id, pkt.destination)
        pkt.next_hop_target = next_hop

        self.pending_forward[pkt.packet_id] = pkt
        self.set_node_color(self.COLOR_FWD_ROUTING)
        self.set_tracked_variable("Estado", f"Encaminhando {pkt.packet_id} -> {next_hop}")

        # Intervalo deliberado por salto para visualização nítida no 3D
        self.provider.schedule_timer(f"fwd:{pkt.packet_id}", now + self.HOP_DELAY)
