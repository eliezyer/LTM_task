from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from rpi5_controller.hardware.gpio import GPIOBackend


@dataclass(order=True)
class _PulseEvent:
    when_s: float
    seq: int
    pin: int = field(compare=False)
    delta: int = field(compare=False)


@dataclass
class PulseScheduler:
    gpio: GPIOBackend
    _events: list[_PulseEvent] = field(default_factory=list)
    _pin_refcounts: dict[int, int] = field(default_factory=dict)
    _sequence: int = 0

    def schedule_pulse(self, pin: int, duration_ms: int, now_s: float) -> None:
        duration_s = max(duration_ms, 0) / 1000.0
        self._schedule_delta(pin=pin, delta=+1, when_s=now_s)
        self._schedule_delta(pin=pin, delta=-1, when_s=now_s + duration_s)

    def schedule_pulse_train(
        self,
        pin: int,
        pulses: int,
        pulse_width_ms: int,
        gap_ms: int,
        now_s: float,
    ) -> None:
        pulse_width_s = max(pulse_width_ms, 0) / 1000.0
        gap_s = max(gap_ms, 0) / 1000.0

        for idx in range(max(0, pulses)):
            start = now_s + idx * (pulse_width_s + gap_s)
            self._schedule_delta(pin=pin, delta=+1, when_s=start)
            self._schedule_delta(pin=pin, delta=-1, when_s=start + pulse_width_s)

    def update(self, now_s: float) -> None:
        while self._events and self._events[0].when_s <= now_s:
            event = heapq.heappop(self._events)
            current = self._pin_refcounts.get(event.pin, 0)
            new_value = max(0, current + event.delta)
            self._pin_refcounts[event.pin] = new_value
            self.gpio.write(event.pin, 1 if new_value > 0 else 0)

    def _schedule_delta(self, pin: int, delta: int, when_s: float) -> None:
        self._sequence += 1
        heapq.heappush(
            self._events,
            _PulseEvent(when_s=when_s, seq=self._sequence, pin=pin, delta=delta),
        )
