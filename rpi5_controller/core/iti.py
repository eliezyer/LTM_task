from __future__ import annotations

import random
from dataclasses import dataclass

from rpi5_controller.core.config import ITIDistributionConfig


@dataclass
class ITISampler:
    config: ITIDistributionConfig
    seed: int | None = None

    def __post_init__(self) -> None:
        self.config.validate()
        self._rng = random.Random(self.seed)

    def sample_seconds(self) -> float:
        if self.config.kind == "uniform":
            return self._rng.uniform(self.config.min_s, self.config.max_s)
        return self._sample_truncated_exponential(
            min_s=self.config.min_s,
            max_s=self.config.max_s,
            mean_s=self.config.mean_s,
        )

    def _sample_truncated_exponential(self, min_s: float, max_s: float, mean_s: float) -> float:
        lam = 1.0 / mean_s
        for _ in range(2048):
            sample = self._rng.expovariate(lam)
            if min_s <= sample <= max_s:
                return sample
        return max(min_s, min(max_s, mean_s))
