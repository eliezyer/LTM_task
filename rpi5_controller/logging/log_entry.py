from __future__ import annotations

import struct
from dataclasses import dataclass

LOG_STRUCT_FORMAT = "<IhfBBBBBB"
LOG_STRUCT = struct.Struct(LOG_STRUCT_FORMAT)


@dataclass(frozen=True)
class LogEntry:
    tick_ms: int
    encoder_count: int
    virtual_pos_cm: float
    state: int
    context_id: int
    lick: int
    reward_on: int
    airpuff_on: int
    flags: int

    def pack(self) -> bytes:
        return LOG_STRUCT.pack(
            self.tick_ms & 0xFFFFFFFF,
            self.encoder_count,
            float(self.virtual_pos_cm),
            self.state & 0xFF,
            self.context_id & 0xFF,
            self.lick & 0xFF,
            self.reward_on & 0xFF,
            self.airpuff_on & 0xFF,
            self.flags & 0xFF,
        )
