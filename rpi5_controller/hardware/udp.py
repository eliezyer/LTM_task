from __future__ import annotations

import socket
from dataclasses import dataclass, field

from rpi5_controller.core.packets import UdpPositionPacket


@dataclass
class UdpSender:
    target_ip: str
    target_port: int
    _socket: socket.socket = field(init=False)

    def __post_init__(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, packet: UdpPositionPacket) -> None:
        self._socket.sendto(packet.pack(), (self.target_ip, self.target_port))

    def close(self) -> None:
        self._socket.close()


@dataclass
class MockUdpSender:
    sent_packets: list[UdpPositionPacket] = field(default_factory=list)

    def send(self, packet: UdpPositionPacket) -> None:
        self.sent_packets.append(packet)

    def close(self) -> None:
        return None
