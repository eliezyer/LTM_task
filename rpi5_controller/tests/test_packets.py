from __future__ import annotations

from rpi5_controller.core.enums import UdpFlags
from rpi5_controller.core.packets import UDP_PACKET_SIZE, UdpPositionPacket


def test_udp_packet_size_is_16_bytes() -> None:
    packet = UdpPositionPacket(seq_num=10, position_cm=12.5, scene_id=2, flags=UdpFlags.TELEPORT)
    raw = packet.pack()
    assert len(raw) == 16
    assert UDP_PACKET_SIZE == 16


def test_udp_packet_uses_padding_for_track_lengths() -> None:
    packet = UdpPositionPacket(
        seq_num=10,
        position_cm=12.5,
        scene_id=2,
        flags=UdpFlags.TELEPORT,
        opening_corridor_length_cm=40.2,
        context_zone_length_cm=120.0,
        outcome_zone_length_cm=30.0,
    )
    raw = packet.pack()

    assert int.from_bytes(raw[10:12], "little") == 40
    assert int.from_bytes(raw[12:14], "little") == 120
    assert int.from_bytes(raw[14:16], "little") == 30
