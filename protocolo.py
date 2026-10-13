from gradysim.protocol.interface import IProtocol

class Protocolo(IProtocol):
    def initialize(self):
        pass

    def handle_timer(self, timer):
        pass

    def handle_packet(self, message):
        pass

    def handle_telemetry(self, telemetry):
        pass

    def finish(self):
        pass
