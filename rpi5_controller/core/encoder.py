from __future__ import annotations

import struct
from dataclasses import dataclass, field

from rpi5_controller.core.packets import EncoderPacket

SYNC_BYTE = 0xAA
PACKET_SIZE = 8


@dataclass
class EncoderPacketParser:
    _buffer: bytearray = field(default_factory=bytearray)

    def feed(self, data: bytes) -> list[EncoderPacket]:
        self._buffer.extend(data)
        packets: list[EncoderPacket] = []

        while len(self._buffer) >= PACKET_SIZE:
            sync_index = self._buffer.find(bytes([SYNC_BYTE]))
            if sync_index < 0:
                self._buffer.clear()
                break

            if sync_index > 0:
                del self._buffer[:sync_index]

            if len(self._buffer) < PACKET_SIZE:
                break

            candidate = self._buffer[:PACKET_SIZE]
            if not self._valid_checksum(candidate):
                del self._buffer[0]
                continue

            packets.append(self._decode_packet(candidate))
            del self._buffer[:PACKET_SIZE]

        return packets

    @staticmethod
    def _valid_checksum(packet: bytes) -> bool:
        checksum = 0
        for byte in packet[1:7]:
            checksum ^= byte
        return checksum == packet[7]

    @staticmethod
    def _decode_packet(packet: bytes) -> EncoderPacket:
        count_u16 = packet[1] | (packet[2] << 8)
        encoder_count = count_u16 - 0x10000 if count_u16 & 0x8000 else count_u16
        timestamp_ms = struct.unpack("<I", packet[3:7])[0]
        return EncoderPacket(encoder_count=encoder_count, timestamp_ms=timestamp_ms)


def build_teensy_packet(encoder_count: int, timestamp_ms: int) -> bytes:
    count_u16 = encoder_count & 0xFFFF
    payload = bytearray(
        [
            SYNC_BYTE,
            count_u16 & 0xFF,
            (count_u16 >> 8) & 0xFF,
        ]
    )
    payload.extend(struct.pack("<I", timestamp_ms & 0xFFFFFFFF))
    checksum = 0
    for byte in payload[1:7]:
        checksum ^= byte
    payload.append(checksum)
    return bytes(payload)
