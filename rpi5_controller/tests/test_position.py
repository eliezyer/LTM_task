from __future__ import annotations

import math

import pytest

from rpi5_controller.core.position import PositionDecoder


def test_position_decoder_uses_wheel_diameter_and_counts_per_revolution() -> None:
    decoder = PositionDecoder(wheel_diameter_cm=19.0, encoder_cpr=256)

    assert decoder.counts_to_cm(256) == pytest.approx(math.pi * 19.0)

    decoder.reset_segment(100)
    assert decoder.segment_position_cm(356) == pytest.approx(math.pi * 19.0)
