# Task Modularity Guide

The task logic is now driven by the session JSON instead of being locked to
exactly three contexts and one hard-coded command order. Old configs still work:
if `contexts`, `context_sequence`, or `task_events` are omitted, the controller
builds the original task:

1. trial start: stop audio, reset segment, teleport, TTL trial start, play
   trial-available cue
2. context entry: reset segment, teleport, play context cue, emit context
   identity pulse train, TTL context entry
3. reward or airpuff at `reward_zone_position_cm`
4. ITI start: stop audio, reset segment, teleport, TTL ITI start

## Core Pieces

Use these JSON sections to change the task:

- `contexts`: which contexts exist and what each context means
- `context_sequence`: optional fixed trial-by-trial context order
- `task_events`: ordered action lists for each trigger point
- `pinmap.wav_cues`: named WAV Trigger input pins for any new audio cues

The built-in trigger points are:

- `trial_start`
- `context_entry`
- `reward`
- `airpuff`
- `iti_start`

You can also define a custom event name in `task_events` and reference it from a
context's `outcome_events`.

## Add Or Remove Contexts

Add a `contexts` list. Each context needs an `id`, `scene_id`, `audio_cue`, and
`identity_pulses`. The cue name must have a pin in `pinmap.wav_cues` unless it is
one of the legacy defaults: `context_1`, `context_2`, or `context_3`.

```json
{
  "contexts": [
    {
      "id": 1,
      "scene_id": 1,
      "audio_cue": "context_1",
      "identity_pulses": 1,
      "reward_ms": 30
    },
    {
      "id": 4,
      "scene_id": 4,
      "audio_cue": "context_4",
      "identity_pulses": 4,
      "airpuff_ms": 50
    }
  ],
  "pinmap": {
    "wav_cues": {
      "context_4": 24
    }
  }
}
```

To remove a context, remove it from `contexts`, `context_sequence`, and any cue
pin you no longer need.

## Fix The Context Order

By default, contexts are block-shuffled without replacement. To force an exact
trial order, add `context_sequence`. It must contain at least `num_trials`
entries; extra entries are ignored.

```json
{
  "num_trials": 6,
  "context_sequence": [1, 4, 1, 4, 4, 1]
}
```

## Change What Happens At A Trigger Point

Override an event in `task_events`. The listed actions run in order.

```json
{
  "task_events": {
    "context_entry": [
      {"type": "ttl_pulse", "event": "context_entry"},
      {"type": "start_audio", "cue": "context"},
      {
        "type": "ttl_pulse_train",
        "event": "context_identity",
        "pulse_count": "context_identity"
      }
    ]
  }
}
```

Use `"cue": "context"` when the cue should resolve to the current context's
`audio_cue`.

## Play Audio Cues Together

Use `cues` instead of `cue`. The controller drives all named WAV Trigger input
lines low at the same time.

```json
{
  "task_events": {
    "context_entry": [
      {"type": "start_audio", "cues": ["trial_available", "context"]},
      {"type": "ttl_pulse", "event": "context_entry"}
    ]
  }
}
```

## Change Outcomes

By default, a context with `airpuff_ms > 0` triggers `airpuff`; otherwise a
context with `reward_ms > 0` triggers `reward`. To run a different outcome list,
set `outcome_events`.

```json
{
  "contexts": [
    {
      "id": 1,
      "scene_id": 1,
      "audio_cue": "context_1",
      "identity_pulses": 1,
      "reward_ms": 30,
      "outcome_events": ["reward", "extra_marker"]
    }
  ],
  "task_events": {
    "extra_marker": [
      {"type": "ttl_pulse", "event": "reward"}
    ]
  }
}
```

Retrieval sessions still suppress context outcomes, preserving the original
retrieval behavior.

## Available Actions

- `stop_audio`
- `start_audio` with `cue` or `cues`
- `reset_segment`
- `teleport`
- `ttl_pulse` with `event`
- `ttl_pulse_train` with `event` and `pulse_count`
- `reward`, using the current context's `reward_ms` unless `duration_ms` is set
- `airpuff`, using the current context's `airpuff_ms` unless `duration_ms` is set

TTL `event` can be `trial_start`, `context_identity`, `context_entry`, `reward`,
`airpuff`, `lick_onset`, or `iti_start`.

## Check A Change

After editing a config:

```bash
python -m rpi5_controller.main --config configs/your_session.json --mock-hardware --max-seconds 5
pytest
```

For hardware line checks:

```bash
python tools/hardware_bringup_check.py --config configs/your_session.json --mock-hardware --yes --skip-lick
```
