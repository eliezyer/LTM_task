from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from rpi5_controller.core.encoder import EncoderPacketParser
from rpi5_controller.core.packets import EncoderPacket


class EncoderReader(Protocol):
    def read_latest_packet(self) -> EncoderPacket | None: ...


class SerialEncoderReader:
    def __init__(self, port: str, baudrate: int):
        try:
            import serial  # type: ignore
        except ImportError as exc:
            raise RuntimeError("pyserial is required for UART access") from exc

        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=0)
        self._parser = EncoderPacketParser()

    def read_latest_packet(self) -> EncoderPacket | None:
        waiting = int(getattr(self._serial, "in_waiting", 0))
        if waiting <= 0:
            return None

        data = self._serial.read(waiting)
        packets = self._parser.feed(data)
        if not packets:
            return None
        return packets[-1]

    def close(self) -> None:
        self._serial.close()


@dataclass
class MockEncoderReader:
    queue: deque[EncoderPacket] = field(default_factory=deque)

    def push(self, packet: EncoderPacket) -> None:
        self.queue.append(packet)

    def read_latest_packet(self) -> EncoderPacket | None:
        if not self.queue:
            return None
        latest = self.queue[-1]
        self.queue.clear()
        return latest


@dataclass
class SyntheticEncoderReader:
    counts_per_second: float
    _count: int = 0
    _last_time_s: float = field(default_factory=time.monotonic)
    _last_timestamp_ms: int = 0

    def read_latest_packet(self) -> EncoderPacket:
        now_s = time.monotonic()
        dt = max(0.0, now_s - self._last_time_s)
        self._last_time_s = now_s

        delta_count = int(round(self.counts_per_second * dt))
        self._count = (self._count + delta_count + 0x8000) % 0x10000 - 0x8000
        self._last_timestamp_ms += int(dt * 1000.0)

        return EncoderPacket(
            encoder_count=self._count,
            timestamp_ms=self._last_timestamp_ms,
        )
