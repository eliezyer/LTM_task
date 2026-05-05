from __future__ import annotations

import json
from pathlib import Path

from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.packets import EncoderPacket
from rpi5_controller.hardware.serial_uart import MockEncoderReader
from rpi5_controller.runtime.session_runner import BehaviorSessionRunner


def test_session_runner_completes_with_mock_hardware(tmp_path: Path, capsys) -> None:
    cfg = SessionConfig.from_dict(
        {
            "animal_id": "m01",
            "session_type": "training",
            "num_trials": 1,
            "reward_ms_by_context": {"1": 10, "2": 10, "3": 10},
            "airpuff_contexts": [],
            "airpuff_duration_ms": 20,
            "iti_distribution": {
                "kind": "uniform",
                "min_s": 0.01,
                "max_s": 0.01,
                "mean_s": 0.01,
            },
            "speed_threshold_cm_s": 0.5,
            "stall_timeout_s": 2.0,
            "opening_corridor_length_cm": 1.0,
            "context_zone_length_cm": 2.0,
            "reward_zone_position_cm": 1.0,
            "wheel_diameter_cm": 20.0,
            "encoder_cpr": 1024,
            "rt_hz": 200,
            "task_status_interval_s": 0.05,
            "seed": 5,
            "output_tmp_dir": str(tmp_path / "tmp"),
            "output_final_dir": str(tmp_path / "final"),
        }
    )

    runner = BehaviorSessionRunner(cfg, use_mock_hardware=True, max_seconds=2.0)
    result = runner.run()

    assert result.trials_completed == 1
    assert result.log_binary_path.exists()
    assert result.log_metadata_path.exists()
    assert result.event_log_path.exists()
    assert result.total_ticks > 0

    events = [
        json.loads(line)
        for line in result.event_log_path.read_text(encoding="utf-8").splitlines()
    ]
    event_names = [event["event"] for event in events]
    assert "trial_start" in event_names
    assert "context_entry" in event_names
    assert "outcome_start" in event_names
    assert "status" in event_names
    assert "trial_complete" in event_names
    assert all("clock_s" in event for event in events)
    assert all("encoder" in event for event in events)
    trial_start = next(event for event in events if event["event"] == "trial_start")
    assert trial_start["trial_index"] == 1
    assert trial_start["context"]["id"] in {1, 2, 3}
    assert "expected_outcome" in trial_start
    status = next(event for event in events if event["event"] == "status")
    assert status["encoder"]["packets_received"] > 0
    assert status["encoder"]["delta_count_since_last_status"] > 0
    stdout = capsys.readouterr().out
    assert "[task]" in stdout
    assert "trial_start" in stdout
    assert "enc=" in stdout


class _KeyboardInterruptEncoderReader:
    def __init__(self) -> None:
        self.calls = 0

    def read_latest_packet(self) -> EncoderPacket | None:
        self.calls += 1
        if self.calls == 1:
            return EncoderPacket(encoder_count=0, timestamp_ms=0)
        raise KeyboardInterrupt

    def close(self) -> None:
        pass


def test_session_runner_stops_gracefully_on_keyboard_interrupt(
    tmp_path: Path,
) -> None:
    cfg = SessionConfig.from_dict(
        {
            "animal_id": "m01",
            "session_type": "training",
            "num_trials": 1,
            "reward_ms_by_context": {"1": 10, "2": 10, "3": 10},
            "iti_distribution": {
                "kind": "uniform",
                "min_s": 0.01,
                "max_s": 0.01,
                "mean_s": 0.01,
            },
            "opening_corridor_length_cm": 1.0,
            "context_zone_length_cm": 2.0,
            "reward_zone_position_cm": 1.0,
            "rt_hz": 200,
            "seed": 5,
            "output_tmp_dir": str(tmp_path / "tmp"),
            "output_final_dir": str(tmp_path / "final"),
        }
    )
    runner = BehaviorSessionRunner(cfg, use_mock_hardware=True)
    runner._encoder_reader = _KeyboardInterruptEncoderReader()

    result = runner.run()

    assert result.stop_reason == "user_interrupt"
    assert result.log_binary_path.exists()
    assert result.log_metadata_path.exists()
    assert result.event_log_path.exists()

    events = [
        json.loads(line)
        for line in result.event_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["event"] == "session_stop"
    assert events[-1]["reason"] == "user_interrupt"


def test_session_runner_unwraps_16_bit_encoder_counts(tmp_path: Path) -> None:
    cfg = SessionConfig.from_dict(
        {
            "animal_id": "m01",
            "session_type": "training",
            "invert_encoder": False,
            "output_tmp_dir": str(tmp_path / "tmp"),
            "output_final_dir": str(tmp_path / "final"),
        }
    )
    runner = BehaviorSessionRunner(cfg, use_mock_hardware=True)
    reader = MockEncoderReader()
    runner._encoder_reader = reader

    reader.push(EncoderPacket(encoder_count=32760, timestamp_ms=0))
    runner._read_latest_encoder_packet(0.0)
    reader.push(EncoderPacket(encoder_count=-32760, timestamp_ms=1))
    runner._read_latest_encoder_packet(0.001)

    assert runner._encoder_count == 32776
