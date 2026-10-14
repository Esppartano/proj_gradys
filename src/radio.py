"""
Meio de comunicação com alcance por enlace.

O `CommunicationMedium` do GrADySim tem um único `transmission_range` para
todos os nós. A BS tem antena de maior alcance (BS_RANGE): qualquer enlace
que tenha a BS numa das pontas usa esse alcance (enlace simétrico).
"""
from dataclasses import replace

from gradysim.simulator.handler.communication import CommunicationHandler

from src.config import BS_RANGE
from src.scenario import BS


class SwarmCommunicationHandler(CommunicationHandler):

    def __init__(self, medium):
        super().__init__(medium)
        self._bs_medium = replace(medium, transmission_range=BS_RANGE)

    def _transmit_message(self, message, source, destination, medium):
        if BS in (source.node.id, destination.node.id):
            medium = self._bs_medium
        super()._transmit_message(message, source, destination, medium)
