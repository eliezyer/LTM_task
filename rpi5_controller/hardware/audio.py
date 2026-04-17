from __future__ import annotations

from dataclasses import dataclass

from rpi5_controller.hardware.gpio import GPIOBackend


@dataclass
class WavTriggerController:
    gpio: GPIOBackend
    trial_available_pin: int
    context_pin_map: dict[int, int]
    active_context: int | None = None
    trial_available_active: bool = False
    _is_setup: bool = False

    def setup(self) -> None:
        for pin in self._all_pins():
            # WAV Trigger Pro inputs are active-low, so keep every line idle-high.
            self.gpio.setup_output(pin, initial=1)
        self._is_setup = True

    def start_trial_available(self) -> None:
        if not self._is_setup:
            raise RuntimeError("WAV trigger GPIO has not been initialized")
        self.stop_all()
        self.gpio.write(self.trial_available_pin, 0)
        self.active_context = None
        self.trial_available_active = True

    def start_context(self, context_id: int) -> None:
        if not self._is_setup:
            raise RuntimeError("WAV trigger GPIO has not been initialized")
        self.stop_all()
        pin = self.context_pin_map[context_id]
        self.gpio.write(pin, 0)
        self.active_context = context_id
        self.trial_available_active = False

    def stop_all(self) -> None:
        if not self._is_setup:
            return
        for pin in self._all_pins():
            self.gpio.write(pin, 1)
        self.trial_available_active = False
        self.active_context = None

    def _all_pins(self) -> tuple[int, ...]:
        return (self.trial_available_pin, *self.context_pin_map.values())
