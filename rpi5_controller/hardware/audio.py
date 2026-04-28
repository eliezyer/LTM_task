from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from rpi5_controller.hardware.gpio import GPIOBackend


@dataclass
class WavTriggerController:
    gpio: GPIOBackend
    trial_available_pin: int | None = None
    context_pin_map: dict[int, int] = field(default_factory=dict)
    cue_pin_map: dict[str, int] = field(default_factory=dict)
    context_cue_map: dict[int, str] = field(default_factory=dict)
    active_context: int | None = None
    trial_available_active: bool = False
    active_cues: set[str] = field(default_factory=set)
    _is_setup: bool = False

    def __post_init__(self) -> None:
        cue_pin_map: dict[str, int] = {}
        if self.trial_available_pin is not None:
            cue_pin_map["trial_available"] = self.trial_available_pin

        context_cue_map = dict(self.context_cue_map)
        for context_id, pin in self.context_pin_map.items():
            cue_id = context_cue_map.get(context_id, f"context_{context_id}")
            context_cue_map[context_id] = cue_id
            cue_pin_map[cue_id] = pin

        cue_pin_map.update(self.cue_pin_map)
        self.context_cue_map = context_cue_map
        self.cue_pin_map = cue_pin_map

    def setup(self) -> None:
        for pin in self._all_pins():
            # WAV Trigger Pro inputs are active-low, so keep every line idle-high.
            self.gpio.setup_output(pin, initial=1)
        self._is_setup = True

    def start_trial_available(self) -> None:
        self.start_cue("trial_available")

    def start_context(self, context_id: int) -> None:
        cue_id = self.context_cue_map.get(context_id, f"context_{context_id}")
        self.start_cue(cue_id)

    def start_cue(self, cue_id: str) -> None:
        self.start_cues((cue_id,))

    def start_cues(self, cue_ids: Iterable[str]) -> None:
        if not self._is_setup:
            raise RuntimeError("WAV trigger GPIO has not been initialized")
        cues = tuple(cue_ids)
        if not cues:
            raise ValueError("At least one cue is required")

        self.stop_all()
        for cue_id in cues:
            pin = self.cue_pin_map[cue_id]
            self.gpio.write(pin, 0)

        self.active_cues = set(cues)
        self.trial_available_active = "trial_available" in self.active_cues

        active_contexts = [
            context_id
            for context_id, cue_id in self.context_cue_map.items()
            if cue_id in self.active_cues
        ]
        self.active_context = active_contexts[0] if len(active_contexts) == 1 else None

    def stop_all(self) -> None:
        if not self._is_setup:
            return
        for pin in self._all_pins():
            self.gpio.write(pin, 1)
        self.trial_available_active = False
        self.active_context = None
        self.active_cues.clear()

    def _all_pins(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(self.cue_pin_map.values()))
