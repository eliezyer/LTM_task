from __future__ import annotations

from rpi5_controller.core.config import ITIDistributionConfig
from rpi5_controller.core.iti import ITISampler


def test_uniform_iti_sampler_respects_bounds() -> None:
    sampler = ITISampler(
        ITIDistributionConfig(kind="uniform", min_s=2.0, max_s=3.0, mean_s=2.5),
        seed=1,
    )
    samples = [sampler.sample_seconds() for _ in range(100)]

    assert all(2.0 <= s <= 3.0 for s in samples)


def test_truncated_exponential_sampler_respects_bounds() -> None:
    sampler = ITISampler(
        ITIDistributionConfig(
            kind="truncated_exponential", min_s=1.0, max_s=2.0, mean_s=1.5
        ),
        seed=2,
    )
    samples = [sampler.sample_seconds() for _ in range(100)]

    assert all(1.0 <= s <= 2.0 for s in samples)
