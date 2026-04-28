from __future__ import annotations

from rpi5_controller.core.randomization import ContextBlockRandomizer


def test_context_block_randomizer_shuffles_without_replacement_per_block() -> None:
    randomizer = ContextBlockRandomizer(num_trials=9, seed=123)
    sequence = randomizer.sequence

    assert len(sequence) == 9
    for i in range(0, 9, 3):
        block = sequence[i : i + 3]
        assert sorted(block) == [1, 2, 3]


def test_context_block_randomizer_can_use_fixed_sequence() -> None:
    randomizer = ContextBlockRandomizer(
        num_trials=4,
        contexts=(10, 20),
        fixed_sequence=(20, 10, 20, 10, 20),
    )

    assert randomizer.sequence == [20, 10, 20, 10]
