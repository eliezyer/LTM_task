from __future__ import annotations

from dataclasses import dataclass

from rpi5_controller.hardware.gpio import GPIOBackend


@dataclass
class LickDetector:
    gpio: GPIOBackend
    pin: int
    _prev_level: int = 0

    def setup(self) -> None:
        self.gpio.setup_input(self.pin)
        self._prev_level = int(self.gpio.read(self.pin))

    def sample(self) -> tuple[int, bool, bool]:
        level = int(self.gpio.read(self.pin))
        onset = self._prev_level == 0 and level == 1
        offset = self._prev_level == 1 and level == 0
        self._prev_level = level
        return level, onset, offset
