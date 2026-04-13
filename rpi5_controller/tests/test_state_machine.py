from __future__ import annotations

from rpi5_controller.core.commands import CommandType, TTLEvent
from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.enums import BehaviorState, SessionType
from rpi5_controller.core.state_machine import BehaviorStateMachine, TickInput


def _has_ttl(commands, event: TTLEvent) -> bool:
    return any(cmd.type == CommandType.TTL_PULSE and cmd.ttl_event == event for cmd in commands)


def _has_command(commands, command_type: CommandType) -> bool:
    return any(cmd.type == command_type for cmd in commands)


def test_start_session_enters_opening(base_config: SessionConfig) -> None:
    sm = BehaviorStateMachine(base_config)
    output = sm.start_session(now_s=0.0)

    assert output.state == BehaviorState.OPENING_CORRIDOR
    assert _has_ttl(output.commands, TTLEvent.TRIAL_START)
    assert _has_command(output.commands, CommandType.RESET_SEGMENT)
    assert _has_command(output.commands, CommandType.AUDIO_START_TRIAL_AVAILABLE)


def test_opening_to_context_transition(base_config: SessionConfig) -> None:
    sm = BehaviorStateMachine(base_config)
    sm.start_session(now_s=0.0)

    output = sm.tick(
        TickInput(
            now_s=0.01,
            segment_position_cm=base_config.opening_corridor_length_cm,
            speed_cm_s=10.0,
            lick_onset=False,
        )
    )

    assert output.state == BehaviorState.CONTEXT_ZONE
    assert output.scene_id in {1, 2, 3}
    assert _has_command(output.commands, CommandType.AUDIO_START_CONTEXT)
    assert any(
        cmd.type == CommandType.TTL_PULSE_TRAIN and cmd.ttl_event == TTLEvent.CONTEXT_IDENTITY
        for cmd in output.commands
    )


def test_retrieval_has_no_feedback() -> None:
    cfg = SessionConfig.from_dict(
        {
            "animal_id": "mouse01",
            "session_type": "retrieval",
            "num_trials": 1,
            "reward_ms_by_context": {"1": 30, "2": 30, "3": 30},
            "airpuff_contexts": [2],
            "airpuff_duration_ms": 30,
            "iti_distribution": {"kind": "uniform", "min_s": 0.1, "max_s": 0.1, "mean_s": 0.1},
            "speed_threshold_cm_s": 1.0,
            "stall_timeout_s": 1.0,
            "opening_corridor_length_cm": 10.0,
            "context_zone_length_cm": 20.0,
            "reward_zone_position_cm": 5.0,
            "wheel_diameter_cm": 20.0,
            "encoder_cpr": 1024,
        }
    )
    sm = BehaviorStateMachine(cfg)
    sm.start_session(now_s=0.0)

    sm.tick(TickInput(now_s=0.05, segment_position_cm=10.0, speed_cm_s=10.0, lick_onset=False))
    output = sm.tick(TickInput(now_s=0.1, segment_position_cm=5.0, speed_cm_s=10.0, lick_onset=False))

    assert output.state == BehaviorState.ITI
    assert not any(cmd.type in {CommandType.SOLENOID_REWARD, CommandType.SOLENOID_AIRPUFF} for cmd in output.commands)
    assert not _has_ttl(output.commands, TTLEvent.REWARD)
    assert not _has_ttl(output.commands, TTLEvent.AIRPUFF)


def test_stall_timeout_enters_iti(base_config: SessionConfig) -> None:
    sm = BehaviorStateMachine(base_config)
    sm.start_session(now_s=0.0)
    sm.tick(TickInput(now_s=0.01, segment_position_cm=10.0, speed_cm_s=10.0, lick_onset=False))

    # Freeze long enough to exceed stall timeout.
    sm.tick(TickInput(now_s=0.02, segment_position_cm=2.0, speed_cm_s=0.0, lick_onset=False))
    output = sm.tick(
        TickInput(
            now_s=0.02 + base_config.stall_timeout_s + 0.01,
            segment_position_cm=2.0,
            speed_cm_s=0.0,
            lick_onset=False,
        )
    )

    assert output.state == BehaviorState.ITI
    assert _has_ttl(output.commands, TTLEvent.ITI_START)
