from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class GPIOBackend(Protocol):
    def setup_output(self, pin: int, initial: int = 0) -> None: ...

    def setup_input(self, pin: int) -> None: ...

    def write(self, pin: int, value: int) -> None: ...

    def read(self, pin: int) -> int: ...

    def cleanup(self) -> None: ...


@dataclass
class MockGPIOBackend:
    pin_modes: dict[int, str] = field(default_factory=dict)
    pin_values: dict[int, int] = field(default_factory=dict)

    def setup_output(self, pin: int, initial: int = 0) -> None:
        self.pin_modes[pin] = "out"
        self.pin_values[pin] = 1 if initial else 0

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
                "An RPi.GPIO-compatible backend is required for real hardware mode; "
                "on Raspberry Pi 5 use rpi-lgpio."
            ) from exc

        self._gpio = gpio
        self._call(self._gpio.setwarnings, False)
        self._call(self._gpio.setmode, self._gpio.BCM)

    def setup_output(self, pin: int, initial: int = 0) -> None:
        initial_level = self._gpio.HIGH if initial else self._gpio.LOW
        self._call(self._gpio.setup, pin, self._gpio.OUT, initial=initial_level)

    def setup_input(self, pin: int) -> None:
        self._call(self._gpio.setup, pin, self._gpio.IN)

    def write(self, pin: int, value: int) -> None:
        self._call(self._gpio.output, pin, self._gpio.HIGH if value else self._gpio.LOW)

    def read(self, pin: int) -> int:
        return int(self._call(self._gpio.input, pin))

    def cleanup(self) -> None:
        self._call(self._gpio.cleanup)

    def _call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as exc:
            translated = self._translate_runtime_error(exc)
            if translated is exc:
                raise
            raise translated from exc

    def _translate_runtime_error(self, exc: RuntimeError) -> RuntimeError:
        detail = str(exc)
        if "Cannot determine SOC peripheral base address" not in detail:
            return exc

        return RuntimeError(
            "GPIO backend failed to access Raspberry Pi hardware. "
            "Raspberry Pi 5 should use the `rpi-lgpio` compatibility package instead "
            "of legacy `RPi.GPIO`. Rebuild the conda environment from "
            "`environment.yml`, or inside the env run "
            "`pip uninstall -y RPi.GPIO && pip install rpi-lgpio`. "
            f"Original error: {detail}"
        )
