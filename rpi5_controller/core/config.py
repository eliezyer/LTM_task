from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rpi5_controller.core.commands import TTLEvent
from rpi5_controller.core.enums import SessionType


DEFAULT_CONTEXT_IDS = (1, 2, 3)
CONTEXT_AUDIO_TOKEN = "context"


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
class TaskActionConfig:
    kind: str
    cue: str | None = None
    cues: tuple[str, ...] = ()
    ttl_event: str | None = None
    duration_ms: int | None = None
    pulse_count: int | str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskActionConfig":
        kind = str(data.get("kind", data.get("type", data.get("action", ""))))
        cues_raw = data.get("cues", ())
        if isinstance(cues_raw, str):
            cues = (cues_raw,)
        else:
            cues = tuple(str(cue) for cue in cues_raw)

        duration_raw = data.get("duration_ms")
        pulse_count_raw = data.get("pulse_count")
        pulse_count: int | str | None
        if isinstance(pulse_count_raw, str):
            pulse_count = pulse_count_raw
        elif pulse_count_raw is None:
            pulse_count = None
        else:
            pulse_count = int(pulse_count_raw)

        action = cls(
            kind=kind,
            cue=str(data["cue"]) if data.get("cue") is not None else None,
            cues=cues,
            ttl_event=str(data.get("ttl_event", data.get("event")))
            if data.get("ttl_event", data.get("event")) is not None
            else None,
            duration_ms=int(duration_raw) if duration_raw is not None else None,
            pulse_count=pulse_count,
        )
        action.validate()
        return action

    def audio_cues(self) -> tuple[str, ...]:
        if self.cues:
            return self.cues
        if self.cue is not None:
            return (self.cue,)
        return ()

    def validate(self) -> None:
        valid_kinds = {
            "airpuff",
            "reset_segment",
            "reward",
            "start_audio",
            "stop_audio",
            "teleport",
            "ttl_pulse",
            "ttl_pulse_train",
        }
        if self.kind not in valid_kinds:
            raise ValueError(f"Unsupported task action kind: {self.kind}")
        if self.kind == "start_audio" and not self.audio_cues():
            raise ValueError("start_audio actions require cue or cues")
        if self.kind in {"ttl_pulse", "ttl_pulse_train"}:
            valid_events = {event.value for event in TTLEvent}
            if self.ttl_event not in valid_events:
                raise ValueError(
                    f"{self.kind} actions require one of these ttl_event values: "
                    f"{sorted(valid_events)}"
                )
        if self.kind == "ttl_pulse_train":
            valid_special_counts = {"context_id", "context_identity"}
            if isinstance(self.pulse_count, str) and self.pulse_count not in valid_special_counts:
                raise ValueError(
                    "ttl_pulse_train pulse_count must be an integer, context_id, "
                    "or context_identity"
                )
        if self.duration_ms is not None and self.duration_ms <= 0:
            raise ValueError("duration_ms must be > 0 when supplied")


@dataclass(frozen=True)
class ContextConfig:
    id: int
    scene_id: int
    audio_cue: str
    identity_pulses: int
    reward_ms: int = 0
    airpuff_ms: int = 0
    outcome_events: tuple[str, ...] = ()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        context_id: int | None = None,
        legacy_reward_ms: int = 0,
        legacy_airpuff_ms: int = 0,
    ) -> "ContextConfig":
        raw_id = data.get("id", context_id)
        if raw_id is None:
            raise ValueError("Context entries require an id")
        ctx_id = int(raw_id)

        outcome_raw = data.get("outcome_events")
        if outcome_raw is None:
            outcome_events: tuple[str, ...] = ()
        elif isinstance(outcome_raw, str):
            outcome_events = (outcome_raw,)
        else:
            outcome_events = tuple(str(event_name) for event_name in outcome_raw)

        cfg = cls(
            id=ctx_id,
            scene_id=int(data.get("scene_id", ctx_id)),
            audio_cue=str(data.get("audio_cue", f"context_{ctx_id}")),
            identity_pulses=int(data.get("identity_pulses", ctx_id)),
            reward_ms=int(data.get("reward_ms", legacy_reward_ms)),
            airpuff_ms=int(data.get("airpuff_ms", legacy_airpuff_ms)),
            outcome_events=outcome_events,
        )
        cfg.validate()
        return cfg

    def resolved_outcome_events(self) -> tuple[str, ...]:
        if self.outcome_events:
            return self.outcome_events
        if self.airpuff_ms > 0:
            return ("airpuff",)
        if self.reward_ms > 0:
            return ("reward",)
        return ()

    def validate(self) -> None:
        if not (1 <= self.id <= 255):
            raise ValueError("context id must be in [1, 255]")
        if not (0 <= self.scene_id <= 255):
            raise ValueError("context scene_id must be in [0, 255]")
        if not self.audio_cue:
            raise ValueError("context audio_cue must not be empty")
        if self.identity_pulses <= 0:
            raise ValueError("context identity_pulses must be > 0")
        if self.reward_ms < 0:
            raise ValueError("context reward_ms must be >= 0")
        if self.airpuff_ms < 0:
            raise ValueError("context airpuff_ms must be >= 0")


def default_task_events() -> dict[str, tuple[TaskActionConfig, ...]]:
    raw_events: dict[str, list[dict[str, Any]]] = {
        "trial_start": [
            {"type": "stop_audio"},
            {"type": "reset_segment"},
            {"type": "teleport"},
            {"type": "ttl_pulse", "event": TTLEvent.TRIAL_START.value},
            {"type": "start_audio", "cue": "trial_available"},
        ],
        "context_entry": [
            {"type": "reset_segment"},
            {"type": "teleport"},
            {"type": "start_audio", "cue": CONTEXT_AUDIO_TOKEN},
            {
                "type": "ttl_pulse_train",
                "event": TTLEvent.CONTEXT_IDENTITY.value,
                "pulse_count": "context_identity",
            },
            {"type": "ttl_pulse", "event": TTLEvent.CONTEXT_ENTRY.value},
        ],
        "reward": [
            {"type": "reward"},
            {"type": "ttl_pulse", "event": TTLEvent.REWARD.value},
        ],
        "airpuff": [
            {"type": "airpuff"},
            {"type": "ttl_pulse", "event": TTLEvent.AIRPUFF.value},
        ],
        "iti_start": [
            {"type": "stop_audio"},
            {"type": "reset_segment"},
            {"type": "teleport"},
            {"type": "ttl_pulse", "event": TTLEvent.ITI_START.value},
        ],
    }
    return {
        event_name: tuple(TaskActionConfig.from_dict(action) for action in actions)
        for event_name, actions in raw_events.items()
    }


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
    wav_cues: dict[str, int] = field(default_factory=dict)
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
        defaults["wav_cues"] = {
            str(cue): int(pin) for cue, pin in defaults.get("wav_cues", {}).items()
        }
        return cls(**defaults)

    def wav_cue_pin_map(self) -> dict[str, int]:
        cue_pins = {
            "trial_available": self.wav_trial_available,
            "context_1": self.wav_context_1,
            "context_2": self.wav_context_2,
            "context_3": self.wav_context_3,
        }
        cue_pins.update(self.wav_cues)
        return cue_pins


@dataclass(frozen=True)
class SessionConfig:
    animal_id: str
    session_type: SessionType
    contexts: dict[int, ContextConfig] = field(default_factory=dict)
    context_sequence: list[int] | None = None
    task_events: dict[str, tuple[TaskActionConfig, ...]] = field(
        default_factory=default_task_events
    )
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
        legacy_airpuff_contexts = [int(ctx) for ctx in data.get("airpuff_contexts", [])]
        airpuff_duration_ms = int(data.get("airpuff_duration_ms", 50))
        contexts = _parse_contexts(
            data.get("contexts"),
            reward_ms_by_context=reward_ms,
            airpuff_contexts=legacy_airpuff_contexts,
            airpuff_duration_ms=airpuff_duration_ms,
        )

        session_type_value = data.get("session_type", SessionType.TRAINING.value)
        pinmap_data = data.get("pinmap", {})
        context_sequence_raw = data.get("context_sequence")
        context_sequence = (
            [int(ctx) for ctx in context_sequence_raw]
            if context_sequence_raw is not None
            else None
        )

        cfg = cls(
            animal_id=str(data.get("animal_id", "unknown")),
            session_type=SessionType(session_type_value),
            contexts=contexts,
            context_sequence=context_sequence,
            task_events=_parse_task_events(data.get("task_events")),
            num_trials=int(data.get("num_trials", 50)),
            reward_ms_by_context={ctx_id: ctx.reward_ms for ctx_id, ctx in contexts.items()},
            airpuff_contexts=[
                ctx_id for ctx_id, ctx in contexts.items() if ctx.airpuff_ms > 0
            ],
            airpuff_duration_ms=airpuff_duration_ms,
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

    @property
    def context_ids(self) -> tuple[int, ...]:
        return tuple(self.contexts.keys())

    @property
    def audio_cue_pin_map(self) -> dict[str, int]:
        return self.pinmap.wav_cue_pin_map()

    @property
    def context_audio_pin_map(self) -> dict[int, int]:
        cue_pins = self.audio_cue_pin_map
        return {
            ctx_id: cue_pins[context.audio_cue]
            for ctx_id, context in self.contexts.items()
        }

    @property
    def context_audio_cue_map(self) -> dict[int, str]:
        return {
            ctx_id: context.audio_cue for ctx_id, context in self.contexts.items()
        }

    def context_config(self, context_id: int) -> ContextConfig:
        return self.contexts[context_id]

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_type"] = self.session_type.value
        return payload

    def validate(self) -> None:
        context_ids = set(self.contexts)

        if not self.animal_id:
            raise ValueError("animal_id must not be empty")
        if self.num_trials <= 0:
            raise ValueError("num_trials must be > 0")
        if not self.contexts:
            raise ValueError("At least one context is required")
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

        if set(self.reward_ms_by_context.keys()) != context_ids:
            raise ValueError("reward_ms_by_context must match configured contexts")
        if any(duration < 0 for duration in self.reward_ms_by_context.values()):
            raise ValueError("reward durations must be >= 0")

        invalid_airpuff = set(self.airpuff_contexts) - context_ids
        if invalid_airpuff:
            raise ValueError(f"airpuff_contexts include invalid IDs: {invalid_airpuff}")

        if self.context_sequence is not None:
            if len(self.context_sequence) < self.num_trials:
                raise ValueError("context_sequence must include at least num_trials entries")
            invalid_sequence_ids = set(self.context_sequence) - context_ids
            if invalid_sequence_ids:
                raise ValueError(
                    f"context_sequence includes invalid IDs: {invalid_sequence_ids}"
                )

        for context in self.contexts.values():
            context.validate()
            missing_events = set(context.resolved_outcome_events()) - set(self.task_events)
            if missing_events:
                raise ValueError(
                    f"context {context.id} references missing outcome_events: "
                    f"{sorted(missing_events)}"
                )

        for event_name, actions in self.task_events.items():
            if not event_name:
                raise ValueError("task event names must not be empty")
            for action in actions:
                action.validate()

        missing_cues = self._referenced_audio_cues() - set(self.audio_cue_pin_map)
        if missing_cues:
            raise ValueError(
                f"Audio cues are referenced but not pinned in pinmap.wav_cues: "
                f"{sorted(missing_cues)}"
            )
        used_audio_pins = [
            self.audio_cue_pin_map[cue] for cue in sorted(self._referenced_audio_cues())
        ]
        if len(set(used_audio_pins)) != len(used_audio_pins):
            raise ValueError("Referenced WAV audio cues must use distinct BCM pins")

        self.iti_distribution.validate()

    def _referenced_audio_cues(self) -> set[str]:
        cues = {context.audio_cue for context in self.contexts.values()}
        for actions in self.task_events.values():
            for action in actions:
                if action.kind != "start_audio":
                    continue
                for cue in action.audio_cues():
                    if cue == CONTEXT_AUDIO_TOKEN:
                        cues.update(context.audio_cue for context in self.contexts.values())
                    else:
                        cues.add(cue)
        return cues


def _parse_contexts(
    raw_contexts: Any,
    *,
    reward_ms_by_context: dict[int, int],
    airpuff_contexts: list[int],
    airpuff_duration_ms: int,
) -> dict[int, ContextConfig]:
    if raw_contexts is None:
        context_ids = tuple(
            sorted(
                set(DEFAULT_CONTEXT_IDS)
                | set(reward_ms_by_context)
                | set(airpuff_contexts)
            )
        )
        return {
            ctx_id: ContextConfig.from_dict(
                {"id": ctx_id},
                legacy_reward_ms=reward_ms_by_context.get(ctx_id, 0),
                legacy_airpuff_ms=airpuff_duration_ms
                if ctx_id in airpuff_contexts
                else 0,
            )
            for ctx_id in context_ids
        }

    items: list[tuple[int | None, Any]]
    if isinstance(raw_contexts, dict):
        items = [(int(ctx_id), context_data) for ctx_id, context_data in raw_contexts.items()]
    else:
        items = [(None, context_data) for context_data in raw_contexts]

    contexts: dict[int, ContextConfig] = {}
    for context_id, context_data in items:
        if isinstance(context_data, int):
            context_data = {"id": context_data}
        if not isinstance(context_data, dict):
            raise ValueError("contexts must contain objects")
        ctx_id = int(context_data.get("id", context_id))
        context = ContextConfig.from_dict(
            context_data,
            context_id=context_id,
            legacy_reward_ms=reward_ms_by_context.get(ctx_id, 0),
            legacy_airpuff_ms=airpuff_duration_ms if ctx_id in airpuff_contexts else 0,
        )
        if context.id in contexts:
            raise ValueError(f"Duplicate context id: {context.id}")
        contexts[context.id] = context
    return contexts


def _parse_task_events(raw_events: Any) -> dict[str, tuple[TaskActionConfig, ...]]:
    events = default_task_events()
    if raw_events is None:
        return events

    for event_name, raw_actions in raw_events.items():
        if raw_actions is None:
            events[str(event_name)] = ()
            continue
        events[str(event_name)] = tuple(
            TaskActionConfig.from_dict(action) for action in raw_actions
        )
    return events


def write_session_config(path: str | Path, config: SessionConfig) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
