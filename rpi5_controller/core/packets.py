from __future__ import annotations

import struct
from dataclasses import dataclass

from rpi5_controller.core.enums import UdpFlags

UDP_PACKET_FORMAT = "<IfBB6x"
UDP_PACKET_SIZE = struct.calcsize(UDP_PACKET_FORMAT)


@dataclass(frozen=True)
class EncoderPacket:
    encoder_count: int
    timestamp_ms: int


@dataclass(frozen=True)
class UdpPositionPacket:
    seq_num: int
    position_cm: float
    scene_id: int
    flags: UdpFlags

    def pack(self) -> bytes:
        return struct.pack(
            UDP_PACKET_FORMAT,
            int(self.seq_num) & 0xFFFFFFFF,
            float(self.position_cm),
            int(self.scene_id) & 0xFF,
            int(self.flags) & 0xFF,
        )
