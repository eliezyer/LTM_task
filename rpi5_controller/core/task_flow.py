from __future__ import annotations

from rpi5_controller.core.commands import Command, CommandType, TTLEvent
from rpi5_controller.core.config import (
    CONTEXT_AUDIO_TOKEN,
    ContextConfig,
    SessionConfig,
    TaskActionConfig,
)


def build_event_commands(
    config: SessionConfig,
    event_name: str,
    *,
    context: ContextConfig | None = None,
) -> list[Command]:
    commands: list[Command] = []
    for action in config.task_events.get(event_name, ()):
        commands.extend(_build_action_commands(action, context=context))
    return commands


def _build_action_commands(
    action: TaskActionConfig,
    *,
    context: ContextConfig | None,
) -> list[Command]:
    if action.kind == "stop_audio":
        return [Command(type=CommandType.AUDIO_STOP_ALL)]
    if action.kind == "reset_segment":
        return [Command(type=CommandType.RESET_SEGMENT)]
    if action.kind == "teleport":
        return [Command(type=CommandType.TELEPORT)]
    if action.kind == "start_audio":
        return [_build_audio_command(action, context=context)]
    if action.kind == "ttl_pulse":
        return [
            Command(
                type=CommandType.TTL_PULSE,
                ttl_event=TTLEvent(action.ttl_event),
                duration_ms=action.duration_ms,
            )
        ]
    if action.kind == "ttl_pulse_train":
        return [
            Command(
                type=CommandType.TTL_PULSE_TRAIN,
                ttl_event=TTLEvent(action.ttl_event),
                pulse_count=_resolve_pulse_count(action, context=context),
            )
        ]
    if action.kind == "reward":
        duration_ms = action.duration_ms
        if duration_ms is None:
            duration_ms = _require_context(context).reward_ms
        if duration_ms <= 0:
            return []
        return [Command(type=CommandType.SOLENOID_REWARD, duration_ms=duration_ms)]
    if action.kind == "airpuff":
        duration_ms = action.duration_ms
        if duration_ms is None:
            duration_ms = _require_context(context).airpuff_ms
        if duration_ms <= 0:
            return []
        return [Command(type=CommandType.SOLENOID_AIRPUFF, duration_ms=duration_ms)]
    raise ValueError(f"Unsupported task action kind: {action.kind}")


def _build_audio_command(
    action: TaskActionConfig,
    *,
    context: ContextConfig | None,
) -> Command:
    cue_ids = tuple(_resolve_cue_id(cue, context=context) for cue in action.audio_cues())
    if cue_ids == ("trial_available",):
        return Command(type=CommandType.AUDIO_START_TRIAL_AVAILABLE)
    if len(cue_ids) == 1 and context is not None and cue_ids[0] == context.audio_cue:
        return Command(type=CommandType.AUDIO_START_CONTEXT, context_id=context.id)
    if len(cue_ids) == 1:
        return Command(type=CommandType.AUDIO_START_CUE, cue_id=cue_ids[0])
    return Command(type=CommandType.AUDIO_START_CUES, cue_ids=cue_ids)


def _resolve_cue_id(cue: str, *, context: ContextConfig | None) -> str:
    if cue != CONTEXT_AUDIO_TOKEN:
        return cue
    return _require_context(context).audio_cue


def _resolve_pulse_count(
    action: TaskActionConfig,
    *,
    context: ContextConfig | None,
) -> int:
    pulse_count = action.pulse_count
    if pulse_count is None:
        return 1
    if isinstance(pulse_count, int):
        return pulse_count
    if pulse_count == "context_id":
        return _require_context(context).id
    if pulse_count == "context_identity":
        return _require_context(context).identity_pulses
    raise ValueError(f"Unsupported pulse_count value: {pulse_count}")


def _require_context(context: ContextConfig | None) -> ContextConfig:
    if context is None:
        raise ValueError("This task action requires a context")
    return context
