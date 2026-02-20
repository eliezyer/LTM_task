from __future__ import annotations

from rpi5_controller.hardware.gpio import MockGPIOBackend
from rpi5_controller.hardware.pulse import PulseScheduler


def test_schedule_single_pulse() -> None:
    gpio = MockGPIOBackend()
    pin = 17
    gpio.setup_output(pin)
    scheduler = PulseScheduler(gpio)

    scheduler.schedule_pulse(pin=pin, duration_ms=5, now_s=1.000)
    scheduler.update(1.000)
    assert gpio.read(pin) == 1

    scheduler.update(1.006)
    assert gpio.read(pin) == 0


def test_schedule_pulse_train() -> None:
    gpio = MockGPIOBackend()
    pin = 18
    gpio.setup_output(pin)
    scheduler = PulseScheduler(gpio)

    scheduler.schedule_pulse_train(pin=pin, pulses=3, pulse_width_ms=5, gap_ms=10, now_s=1.000)

    scheduler.update(1.000)
    assert gpio.read(pin) == 1

    scheduler.update(1.006)
    assert gpio.read(pin) == 0

    scheduler.update(1.016)
    assert gpio.read(pin) == 1
