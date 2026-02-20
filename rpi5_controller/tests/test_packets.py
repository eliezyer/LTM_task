from __future__ import annotations

from rpi5_controller.core.enums import UdpFlags
from rpi5_controller.core.packets import UDP_PACKET_SIZE, UdpPositionPacket


def test_udp_packet_size_is_16_bytes() -> None:
    packet = UdpPositionPacket(seq_num=10, position_cm=12.5, scene_id=2, flags=UdpFlags.TELEPORT)
    raw = packet.pack()
    assert len(raw) == 16
    assert UDP_PACKET_SIZE == 16
