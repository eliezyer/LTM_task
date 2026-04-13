from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rpi5_controller.core.enums import SessionType


@dataclass(frozen=True)
class ITIDistributionConfig:
    kind: str = "uniform"
    min_s: float = 2.0
    max_s: float = 4.0
    mean_s: float = 3.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ITIDistributionConfig":
        return cls(
            kind=str(data.get("kind", "uniform")),
            min_s=float(data.get("min_s", 2.0)),
            max_s=float(data.get("max_s", 4.0)),
            mean_s=float(data.get("mean_s", 3.0)),
        )

    def validate(self) -> None:
        if self.kind not in {"uniform", "truncated_exponential"}:
            raise ValueError(f"Unsupported ITI distribution kind: {self.kind}")
        if self.min_s <= 0:
            raise ValueError("ITI min_s must be > 0")
        if self.max_s < self.min_s:
            raise ValueError("ITI max_s must be >= min_s")
        if self.mean_s <= 0:
            raise ValueError("ITI mean_s must be > 0")


@dataclass(frozen=True)
class PinMap:
    uart_tx: int = 14
    uart_rx: int = 15
    water_solenoid: int = 4
    air_solenoid: int = 5
    wav_trial_available: int = 6
    wav_context_1: int = 7
    wav_context_2: int = 8
    wav_context_3: int = 13
    lick_input: int = 9
    ttl_trial_start: int = 17
    ttl_context_identity: int = 18
    ttl_context_entry: int = 19
    ttl_reward: int = 20
    ttl_airpuff: int = 21
    ttl_lick: int = 22
    ttl_iti_start: int = 23

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PinMap":
        defaults = asdict(cls())
        defaults.update(data)
        return cls(**defaults)


@dataclass(frozen=True)
class SessionConfig:
    animal_id: str
    session_type: SessionType
    num_trials: int = 50
    reward_ms_by_context: dict[int, int] = field(
        default_factory=lambda: {1: 30, 2: 0, 3: 30}
    )
    airpuff_contexts: list[int] = field(default_factory=list)
    airpuff_duration_ms: int = 50
    iti_distribution: ITIDistributionConfig = field(default_factory=ITIDistributionConfig)
    speed_threshold_cm_s: float = 1.0
    stall_timeout_s: float = 3.0
    opening_corridor_length_cm: float = 60.0
    context_zone_length_cm: float = 120.0
    reward_zone_position_cm: float = 100.0
    wheel_diameter_cm: float = 20.0
    encoder_cpr: int = 1024
    speed_alpha: float = 0.2
    udp_target_ip: str = "192.168.10.2"
    udp_target_port: int = 5005
    serial_port: str = "/dev/serial0"
    serial_baud: int = 1_000_000
    rt_hz: int = 1000
    ttl_pulse_width_ms: int = 5
    ttl_train_gap_ms: int = 10
    output_tmp_dir: str = "/tmp/bhv_log"
    output_final_dir: str = "logs"
    seed: int | None = None
    pinmap: PinMap = field(default_factory=PinMap)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionConfig":
        reward_ms_raw = data.get("reward_ms_by_context", {1: 30, 2: 0, 3: 30})
        reward_ms = {
            int(ctx): int(duration_ms) for ctx, duration_ms in reward_ms_raw.items()
        }
        airpuff_contexts = [int(ctx) for ctx in data.get("airpuff_contexts", [])]

        session_type_value = data.get("session_type", SessionType.TRAINING.value)
        pinmap_data = data.get("pinmap", {})

        cfg = cls(
            animal_id=str(data.get("animal_id", "unknown")),
            session_type=SessionType(session_type_value),
            num_trials=int(data.get("num_trials", 50)),
            reward_ms_by_context=reward_ms,
            airpuff_contexts=airpuff_contexts,
            airpuff_duration_ms=int(data.get("airpuff_duration_ms", 50)),
            iti_distribution=ITIDistributionConfig.from_dict(
                data.get("iti_distribution", {})
            ),
            speed_threshold_cm_s=float(data.get("speed_threshold_cm_s", 1.0)),
            stall_timeout_s=float(data.get("stall_timeout_s", 3.0)),
            opening_corridor_length_cm=float(
                data.get("opening_corridor_length_cm", 60.0)
            ),
            context_zone_length_cm=float(data.get("context_zone_length_cm", 120.0)),
            reward_zone_position_cm=float(data.get("reward_zone_position_cm", 100.0)),
            wheel_diameter_cm=float(data.get("wheel_diameter_cm", 20.0)),
            encoder_cpr=int(data.get("encoder_cpr", 1024)),
            speed_alpha=float(data.get("speed_alpha", 0.2)),
            udp_target_ip=str(data.get("udp_target_ip", "192.168.10.2")),
            udp_target_port=int(data.get("udp_target_port", 5005)),
            serial_port=str(data.get("serial_port", "/dev/serial0")),
            serial_baud=int(data.get("serial_baud", 1_000_000)),
            rt_hz=int(data.get("rt_hz", 1000)),
            ttl_pulse_width_ms=int(data.get("ttl_pulse_width_ms", 5)),
            ttl_train_gap_ms=int(data.get("ttl_train_gap_ms", 10)),
            output_tmp_dir=str(data.get("output_tmp_dir", "/tmp/bhv_log")),
            output_final_dir=str(data.get("output_final_dir", "logs")),
            seed=int(data["seed"]) if data.get("seed") is not None else None,
            pinmap=PinMap.from_dict(pinmap_data),
        )
        cfg.validate()
        return cfg

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SessionConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_type"] = self.session_type.value
        return payload

    def validate(self) -> None:
        contexts = {1, 2, 3}
        audio_pins = {
            self.pinmap.wav_trial_available,
            self.pinmap.wav_context_1,
            self.pinmap.wav_context_2,
            self.pinmap.wav_context_3,
        }

        if not self.animal_id:
            raise ValueError("animal_id must not be empty")
        if self.num_trials <= 0:
            raise ValueError("num_trials must be > 0")
        if self.airpuff_duration_ms <= 0:
            raise ValueError("airpuff_duration_ms must be > 0")
        if self.speed_threshold_cm_s < 0:
            raise ValueError("speed_threshold_cm_s must be >= 0")
        if self.stall_timeout_s <= 0:
            raise ValueError("stall_timeout_s must be > 0")
        if self.opening_corridor_length_cm <= 0:
            raise ValueError("opening_corridor_length_cm must be > 0")
        if self.context_zone_length_cm <= 0:
            raise ValueError("context_zone_length_cm must be > 0")
        if not (0 < self.reward_zone_position_cm <= self.context_zone_length_cm):
            raise ValueError(
                "reward_zone_position_cm must be > 0 and <= context_zone_length_cm"
            )
        if self.wheel_diameter_cm <= 0:
            raise ValueError("wheel_diameter_cm must be > 0")
        if self.encoder_cpr <= 0:
            raise ValueError("encoder_cpr must be > 0")
        if not (0.0 < self.speed_alpha <= 1.0):
            raise ValueError("speed_alpha must be in (0, 1]")
        if self.rt_hz <= 0:
            raise ValueError("rt_hz must be > 0")
        if self.ttl_pulse_width_ms <= 0:
            raise ValueError("ttl_pulse_width_ms must be > 0")
        if self.ttl_train_gap_ms < 0:
            raise ValueError("ttl_train_gap_ms must be >= 0")

        if set(self.reward_ms_by_context.keys()) != contexts:
            raise ValueError("reward_ms_by_context must include exactly contexts 1, 2, 3")
        if any(duration < 0 for duration in self.reward_ms_by_context.values()):
            raise ValueError("reward durations must be >= 0")

        invalid_airpuff = set(self.airpuff_contexts) - contexts
        if invalid_airpuff:
            raise ValueError(f"airpuff_contexts include invalid IDs: {invalid_airpuff}")
        if len(audio_pins) != 4:
            raise ValueError(
                "WAV trigger outputs must use four distinct BCM pins: "
                "trial_available, context 1, context 2, context 3"
            )

        self.iti_distribution.validate()


def write_session_config(path: str | Path, config: SessionConfig) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
