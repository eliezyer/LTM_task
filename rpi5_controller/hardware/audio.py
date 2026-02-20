from __future__ import annotations

from dataclasses import dataclass

from rpi5_controller.hardware.gpio import GPIOBackend


@dataclass
class WavTriggerController:
    gpio: GPIOBackend
    context_pin_map: dict[int, int]
    active_context: int | None = None

    def setup(self) -> None:
        for pin in self.context_pin_map.values():
            self.gpio.setup_output(pin)
            self.gpio.write(pin, 0)

    def start_context(self, context_id: int) -> None:
        self.stop_all()
        pin = self.context_pin_map[context_id]
        self.gpio.write(pin, 1)
        self.active_context = context_id

    def stop_all(self) -> None:
        for pin in self.context_pin_map.values():
            self.gpio.write(pin, 0)
        self.active_context = None
