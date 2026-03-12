from __future__ import annotations

import pytest

from rpi5_controller.hardware.audio import WavTriggerController
from rpi5_controller.hardware.gpio import MockGPIOBackend


def test_stop_all_before_setup_is_noop() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(gpio=gpio, context_pin_map={1: 6, 2: 7, 3: 8})

    audio.stop_all()

    assert audio.active_context is None
    assert gpio.pin_modes == {}


def test_start_context_requires_setup() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(gpio=gpio, context_pin_map={1: 6, 2: 7, 3: 8})

    with pytest.raises(RuntimeError, match="has not been initialized"):
        audio.start_context(1)
