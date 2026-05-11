from __future__ import annotations

import struct
from dataclasses import dataclass

from rpi5_controller.core.enums import UdpFlags

UDP_PACKET_FORMAT = "<IfBBHHH"
UDP_PACKET_SIZE = struct.calcsize(UDP_PACKET_FORMAT)
MAX_UDP_TRACK_LENGTH_CM = 65535


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
    opening_corridor_length_cm: float = 0.0
    context_zone_length_cm: float = 0.0
    outcome_zone_length_cm: float = 0.0

    def pack(self) -> bytes:
        return struct.pack(
            UDP_PACKET_FORMAT,
            int(self.seq_num) & 0xFFFFFFFF,
            float(self.position_cm),
            int(self.scene_id) & 0xFF,
            int(self.flags) & 0xFF,
            _length_cm_to_uint16(self.opening_corridor_length_cm),
            _length_cm_to_uint16(self.context_zone_length_cm),
            _length_cm_to_uint16(self.outcome_zone_length_cm),
        )


def _length_cm_to_uint16(length_cm: float) -> int:
    if length_cm <= 0:
        return 0
    return min(MAX_UDP_TRACK_LENGTH_CM, max(1, int(round(length_cm))))
