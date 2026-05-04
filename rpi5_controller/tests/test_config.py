from __future__ import annotations

from rpi5_controller.core.config import SessionConfig


def test_encoder_inversion_defaults_to_current_rig_direction() -> None:
    cfg = SessionConfig.from_dict({"animal_id": "m01"})

    assert cfg.invert_encoder is True


def test_encoder_inversion_can_be_disabled() -> None:
    cfg = SessionConfig.from_dict({"animal_id": "m01", "invert_encoder": False})

    assert cfg.invert_encoder is False
