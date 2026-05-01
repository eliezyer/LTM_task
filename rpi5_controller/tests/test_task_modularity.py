from __future__ import annotations

from rpi5_controller.core.commands import CommandType, TTLEvent
from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.enums import BehaviorState
from rpi5_controller.core.state_machine import BehaviorStateMachine, TickInput


def _modular_config() -> SessionConfig:
    return SessionConfig.from_dict(
        {
            "animal_id": "mouse_modular",
            "session_type": "training",
            "num_trials": 4,
            "contexts": [
                {
                    "id": 10,
                    "scene_id": 4,
                    "audio_cue": "forest",
                    "identity_pulses": 1,
                    "reward_ms": 12,
                },
                {
                    "id": 20,
                    "scene_id": 5,
                    "audio_cue": "desert",
                    "identity_pulses": 2,
                    "airpuff_ms": 8,
                },
            ],
            "context_sequence": [20, 10, 20, 10],
            "task_events": {
                "context_entry": [
                    {"type": "ttl_pulse", "event": "context_entry"},
                    {"type": "start_audio", "cues": ["trial_available", "context"]},
                    {
                        "type": "ttl_pulse_train",
                        "event": "context_identity",
                        "pulse_count": "context_identity",
                    },
                ]
            },
            "pinmap": {
                "wav_cues": {
                    "forest": 25,
                    "desert": 26,
                }
            },
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
        }
    )


def test_config_supports_custom_contexts_cues_and_fixed_sequence() -> None:
    cfg = _modular_config()

    assert cfg.context_ids == (10, 20)
    assert cfg.context_audio_pin_map == {10: 25, 20: 26}
    assert cfg.context_config(20).resolved_outcome_events() == ("airpuff",)
    assert cfg.reward_ms_by_context == {10: 12, 20: 0}
    assert cfg.airpuff_contexts == [20]


def test_state_machine_uses_configured_event_order_and_coplayed_audio() -> None:
    cfg = _modular_config()
    sm = BehaviorStateMachine(cfg)

    assert sm.planned_context_sequence == [20, 10, 20, 10]

    sm.start_session(now_s=0.0)
    output = sm.tick(
        TickInput(
            now_s=0.01,
            segment_position_cm=cfg.opening_corridor_length_cm,
            speed_cm_s=10.0,
            lick_onset=False,
        )
    )

    assert output.state == BehaviorState.CONTEXT_ZONE
    assert output.context_id == 20
    assert output.scene_id == 5
    assert output.commands[0].type == CommandType.TTL_PULSE
    assert output.commands[0].ttl_event == TTLEvent.CONTEXT_ENTRY
    assert output.commands[1].type == CommandType.AUDIO_START_CUES
    assert output.commands[1].cue_ids == ("trial_available", "desert")
    assert output.commands[2].type == CommandType.TTL_PULSE_TRAIN
    assert output.commands[2].pulse_count == 2
