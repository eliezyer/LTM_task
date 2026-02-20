from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class GPIOBackend(Protocol):
    def setup_output(self, pin: int) -> None: ...

    def setup_input(self, pin: int) -> None: ...

    def write(self, pin: int, value: int) -> None: ...

    def read(self, pin: int) -> int: ...

    def cleanup(self) -> None: ...


@dataclass
class MockGPIOBackend:
    pin_modes: dict[int, str] = field(default_factory=dict)
    pin_values: dict[int, int] = field(default_factory=dict)

    def setup_output(self, pin: int) -> None:
        self.pin_modes[pin] = "out"
        self.pin_values.setdefault(pin, 0)

    def setup_input(self, pin: int) -> None:
        self.pin_modes[pin] = "in"
        self.pin_values.setdefault(pin, 0)

    def write(self, pin: int, value: int) -> None:
        if self.pin_modes.get(pin) != "out":
            raise RuntimeError(f"Pin {pin} is not configured as output")
        self.pin_values[pin] = 1 if value else 0

    def read(self, pin: int) -> int:
        return int(self.pin_values.get(pin, 0))

    def set_input_value(self, pin: int, value: int) -> None:
        if self.pin_modes.get(pin) != "in":
            raise RuntimeError(f"Pin {pin} is not configured as input")
        self.pin_values[pin] = 1 if value else 0

    def cleanup(self) -> None:
        self.pin_modes.clear()
        self.pin_values.clear()


class RPiGPIOBackend:
    def __init__(self) -> None:
        try:
            import RPi.GPIO as gpio  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "RPi.GPIO is required for real hardware mode; install it on Raspberry Pi"
            ) from exc

        self._gpio = gpio
        self._gpio.setwarnings(False)
        self._gpio.setmode(self._gpio.BCM)

    def setup_output(self, pin: int) -> None:
        self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)

    def setup_input(self, pin: int) -> None:
        self._gpio.setup(pin, self._gpio.IN)

    def write(self, pin: int, value: int) -> None:
        self._gpio.output(pin, self._gpio.HIGH if value else self._gpio.LOW)

    def read(self, pin: int) -> int:
        return int(self._gpio.input(pin))

    def cleanup(self) -> None:
        self._gpio.cleanup()
