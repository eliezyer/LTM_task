from __future__ import annotations

import pytest

from rpi5_controller.core.config import SessionConfig


@pytest.fixture
def base_config() -> SessionConfig:
    return SessionConfig.from_dict(
        {
            "animal_id": "mouse01",
            "session_type": "training",
            "num_trials": 6,
            "reward_ms_by_context": {"1": 30, "2": 0, "3": 30},
            "airpuff_contexts": [2],
            "airpuff_duration_ms": 40,
            "iti_distribution": {
                "kind": "uniform",
                "min_s": 0.1,
                "max_s": 0.1,
                "mean_s": 0.1,
            },
            "speed_threshold_cm_s": 1.0,
            "stall_timeout_s": 0.2,
            "opening_corridor_length_cm": 10.0,
            "context_zone_length_cm": 20.0,
            "reward_zone_position_cm": 5.0,
            "wheel_diameter_cm": 20.0,
            "encoder_cpr": 1024,
            "speed_alpha": 0.2,
            "seed": 7,
            "output_tmp_dir": "/tmp/bhv_log_test",
            "output_final_dir": "/tmp/bhv_log_test_final"
        }
    )
