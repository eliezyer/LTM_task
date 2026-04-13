from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandType(str, Enum):
    RESET_SEGMENT = "reset_segment"
    TELEPORT = "teleport"
    AUDIO_START_TRIAL_AVAILABLE = "audio_start_trial_available"
    AUDIO_START_CONTEXT = "audio_start_context"
    AUDIO_STOP_ALL = "audio_stop_all"
    SOLENOID_REWARD = "solenoid_reward"
    SOLENOID_AIRPUFF = "solenoid_airpuff"
    TTL_PULSE = "ttl_pulse"
    TTL_PULSE_TRAIN = "ttl_pulse_train"


class TTLEvent(str, Enum):
    TRIAL_START = "trial_start"
    CONTEXT_IDENTITY = "context_identity"
    CONTEXT_ENTRY = "context_entry"
    REWARD = "reward"
    AIRPUFF = "airpuff"
    LICK_ONSET = "lick_onset"
    ITI_START = "iti_start"


@dataclass(frozen=True)
class Command:
    type: CommandType
    ttl_event: TTLEvent | None = None
    context_id: int | None = None
    duration_ms: int | None = None
    pulse_count: int | None = None
