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


@dataclass
class SquareWaveDigitalOutput:
    gpio: GPIOBackend
    pin: int
    frequency_hz: float
    duty_cycle: float = 0.5
    enabled: bool = True
    _period_s: float = field(init=False)
    _high_s: float = field(init=False)
    _start_s: float | None = None
    _last_value: int = 0

    def __post_init__(self) -> None:
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        if not (0.0 < self.duty_cycle < 1.0):
            raise ValueError("duty_cycle must be in (0, 1)")
        self._period_s = 1.0 / self.frequency_hz
        self._high_s = self._period_s * self.duty_cycle

    def update(self, now_s: float) -> None:
        if not self.enabled:
            self.stop()
            return

        if self._start_s is None:
            self._start_s = now_s

        phase_s = (now_s - self._start_s) % self._period_s
        value = 1 if phase_s < self._high_s else 0
        if value != self._last_value:
            self.gpio.write(self.pin, value)
            self._last_value = value

    def stop(self) -> None:
        self._start_s = None
        if self._last_value != 0:
            self.gpio.write(self.pin, 0)
            self._last_value = 0
