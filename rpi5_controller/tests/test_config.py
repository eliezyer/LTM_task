from __future__ import annotations

from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.enums import SessionType


def test_encoder_inversion_defaults_to_current_rig_direction() -> None:
    cfg = SessionConfig.from_dict({"animal_id": "m01"})

    assert cfg.invert_encoder is True


def test_encoder_inversion_can_be_disabled() -> None:
    cfg = SessionConfig.from_dict({"animal_id": "m01", "invert_encoder": False})

    assert cfg.invert_encoder is False


def test_habituation_config_file_parses() -> None:
    cfg = SessionConfig.from_json_file("configs/habituation_session.json")

    assert cfg.session_type == SessionType.HABITUATION
    assert cfg.context_sequence[:6] == [1, 2, 3, 1, 2, 3]
    assert cfg.outcome_zone_length_cm == 30.0
