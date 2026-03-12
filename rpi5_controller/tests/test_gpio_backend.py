from __future__ import annotations

import sys
from types import ModuleType

import pytest

from rpi5_controller.hardware.gpio import RPiGPIOBackend


def test_gpio_backend_translates_pi5_soc_error(monkeypatch: pytest.MonkeyPatch) -> None:
    gpio_module = ModuleType("RPi.GPIO")
    gpio_module.BCM = 11
    gpio_module.OUT = 0
    gpio_module.IN = 1
    gpio_module.LOW = 0
    gpio_module.HIGH = 1
    gpio_module.setwarnings = lambda _flag: None
    gpio_module.setmode = lambda _mode: None
    gpio_module.output = lambda _pin, _value: None
    gpio_module.input = lambda _pin: 0
    gpio_module.cleanup = lambda: None

    def fail_setup(*_args, **_kwargs):
        raise RuntimeError("Cannot determine SOC peripheral base address")

    gpio_module.setup = fail_setup

    rpi_package = ModuleType("RPi")
    rpi_package.GPIO = gpio_module

    monkeypatch.setitem(sys.modules, "RPi", rpi_package)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", gpio_module)

    backend = RPiGPIOBackend()

    with pytest.raises(RuntimeError, match="rpi-lgpio"):
        backend.setup_output(17)
