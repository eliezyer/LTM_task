from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class ContextBlockRandomizer:
    num_trials: int
    contexts: tuple[int, ...] = (1, 2, 3)
    seed: int | None = None
    fixed_sequence: tuple[int, ...] | None = None
    _sequence: list[int] = field(default_factory=list)
    _index: int = 0

    def __post_init__(self) -> None:
        if self.num_trials <= 0:
            raise ValueError("num_trials must be > 0")
        if not self.contexts:
            raise ValueError("contexts must not be empty")
        if self.fixed_sequence is not None:
            self._sequence = self._prepare_fixed_sequence()
        else:
            self._sequence = self._generate_sequence()

    def _prepare_fixed_sequence(self) -> list[int]:
        if len(self.fixed_sequence or ()) < self.num_trials:
            raise ValueError("fixed_sequence must include at least num_trials entries")
        invalid_contexts = set(self.fixed_sequence or ()) - set(self.contexts)
        if invalid_contexts:
            raise ValueError(f"fixed_sequence includes invalid contexts: {invalid_contexts}")
        return list((self.fixed_sequence or ())[: self.num_trials])

    def _generate_sequence(self) -> list[int]:
        rng = random.Random(self.seed)
        sequence: list[int] = []
        while len(sequence) < self.num_trials:
            block = list(self.contexts)
            rng.shuffle(block)
            sequence.extend(block)
        return sequence[: self.num_trials]

    @property
    def sequence(self) -> list[int]:
        return list(self._sequence)

    def next_context(self) -> int:
        if self._index >= len(self._sequence):
            raise IndexError("Context sequence exhausted")
        ctx = self._sequence[self._index]
        self._index += 1
        return ctx
