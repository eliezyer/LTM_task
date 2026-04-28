from __future__ import annotations

import pytest

from rpi5_controller.hardware.audio import WavTriggerController
from rpi5_controller.hardware.gpio import MockGPIOBackend


def test_stop_all_before_setup_is_noop() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(
        gpio=gpio,
        trial_available_pin=6,
        context_pin_map={1: 7, 2: 8, 3: 13},
    )

    audio.stop_all()

    assert audio.active_context is None
    assert not audio.trial_available_active
    assert gpio.pin_modes == {}


def test_start_context_requires_setup() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(
        gpio=gpio,
        trial_available_pin=6,
        context_pin_map={1: 7, 2: 8, 3: 13},
    )

    with pytest.raises(RuntimeError, match="has not been initialized"):
        audio.start_context(1)


def test_setup_idles_all_audio_pins_high() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(
        gpio=gpio,
        trial_available_pin=6,
        context_pin_map={1: 7, 2: 8, 3: 13},
    )

    audio.setup()

    assert gpio.pin_values == {6: 1, 7: 1, 8: 1, 13: 1}


def test_trial_available_switches_to_context_cue() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(
        gpio=gpio,
        trial_available_pin=6,
        context_pin_map={1: 7, 2: 8, 3: 13},
    )

    audio.setup()
    audio.start_trial_available()

    assert gpio.pin_values[6] == 0
    assert gpio.pin_values[7] == 1
    assert gpio.pin_values[8] == 1
    assert gpio.pin_values[13] == 1
    assert audio.trial_available_active
    assert audio.active_context is None

    audio.start_context(2)

    assert gpio.pin_values[6] == 1
    assert gpio.pin_values[7] == 1
    assert gpio.pin_values[8] == 0
    assert gpio.pin_values[13] == 1
    assert not audio.trial_available_active
    assert audio.active_context == 2

    audio.stop_all()

    assert gpio.pin_values == {6: 1, 7: 1, 8: 1, 13: 1}
    assert audio.active_context is None
    assert not audio.trial_available_active


def test_start_cues_can_play_multiple_audio_lines_together() -> None:
    gpio = MockGPIOBackend()
    audio = WavTriggerController(
        gpio=gpio,
        trial_available_pin=6,
        cue_pin_map={"tone_a": 11, "tone_b": 12},
    )

    audio.setup()
    audio.start_cues(("tone_a", "tone_b"))

    assert gpio.pin_values[6] == 1
    assert gpio.pin_values[11] == 0
    assert gpio.pin_values[12] == 0
    assert audio.active_cues == {"tone_a", "tone_b"}
    assert audio.active_context is None
    assert not audio.trial_available_active
