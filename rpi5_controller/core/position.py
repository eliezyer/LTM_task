from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PositionDecoder:
    wheel_diameter_cm: float
    encoder_cpr: int
    segment_offset_count: int = 0

    @property
    def wheel_circumference_cm(self) -> float:
        return math.pi * self.wheel_diameter_cm

    def counts_to_cm(self, counts: int) -> float:
        return (counts * self.wheel_circumference_cm) / self.encoder_cpr

    def reset_segment(self, current_count: int) -> None:
        self.segment_offset_count = current_count

    def segment_position_cm(self, current_count: int) -> float:
        return self.counts_to_cm(current_count - self.segment_offset_count)


@dataclass
class SpeedEstimator:
    wheel_diameter_cm: float
    encoder_cpr: int
    alpha: float = 0.2
    _prev_count: int | None = None
    _prev_time_s: float | None = None
    _speed_filtered: float = 0.0

    @property
    def wheel_circumference_cm(self) -> float:
        return math.pi * self.wheel_diameter_cm

    def update(self, encoder_count: int, now_s: float) -> float:
        if self._prev_count is None or self._prev_time_s is None:
            self._prev_count = encoder_count
            self._prev_time_s = now_s
            return self._speed_filtered

        dt_s = now_s - self._prev_time_s
        if dt_s <= 0:
            return self._speed_filtered

        delta_count = encoder_count - self._prev_count
        raw_speed = (delta_count * self.wheel_circumference_cm) / (self.encoder_cpr * dt_s)
        self._speed_filtered = (
            self.alpha * raw_speed + (1.0 - self.alpha) * self._speed_filtered
        )

        self._prev_count = encoder_count
        self._prev_time_s = now_s
        return self._speed_filtered
