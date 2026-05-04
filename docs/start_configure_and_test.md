# Start, Configure, And Test A Task Session

This guide walks through the normal loop for starting a behavioral task session,
changing what happens in the session config, and running a safe end-to-end test.
Run commands from the repository root unless a command says otherwise.

## 1. Set Up The Python Environment

Create and activate a local environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

If the environment already exists, activate it before running tools:

```bash
source .venv/bin/activate
```

## 2. Create Or Pick A Session Config

Session behavior is controlled by JSON files in `configs/`. Start with one of
these paths:

- Use the checked-in example: `configs/example_session.json`
- Generate a new config interactively:

```bash
python tools/configure_session.py
```

The generator asks for the animal ID, session type, number of trials, context
IDs, reward and airpuff settings, corridor lengths, encoder settings, output
log directories, and audio trigger pins. It writes a timestamped file like:

```text
configs/session_<animal_id>_<YYYYMMDD_HHMMSS>.json
```

To generate and immediately launch after confirmation:

```bash
python tools/configure_session.py --auto-launch
```

Use the interactive generator for routine sessions. Edit the JSON file directly
when you need exact trial order, custom contexts, custom task events, or hardware
pin changes.

## 3. Change Basic Session Parameters

Open the session JSON in `configs/` and edit the fields you need. Common fields:

| Field | What it changes |
| --- | --- |
| `animal_id` | Animal/session label used in output log filenames. |
| `session_type` | `training`, `retrieval`, or `retraining`. Retrieval skips context outcomes. |
| `num_trials` | Number of trials to run before the session exits. |
| `seed` | Randomization seed. Use `null` for system randomness. |
| `iti_distribution.kind` | `uniform` or `truncated_exponential`. |
| `iti_distribution.min_s`, `max_s`, `mean_s` | ITI timing in seconds. |
| `speed_threshold_cm_s` | Movement threshold used for trial initiation logic. |
| `stall_timeout_s` | Time spent stalled in the context zone before moving to ITI. |
| `opening_corridor_length_cm` | Distance before the context starts. |
| `context_zone_length_cm` | Length of the context segment. |
| `reward_zone_position_cm` | Position inside the context where outcomes are triggered. Must be <= `context_zone_length_cm`. |
| `outcome_zone_duration_s` | Duration of the outcome scene/TTL hold. |
| `outcome_scene_id` | Unity scene ID during the outcome zone. |
| `wheel_diameter_cm`, `encoder_cpr`, `speed_alpha` | Encoder decoding and speed smoothing. |
| `invert_encoder` | Defaults to `true` for the current rig. Set to `false` only if wheel movement prints negative position/count changes. |
| `task_status_interval_s` | How often the terminal and `.events.jsonl` log receive status updates during a run. |
| `udp_target_ip`, `udp_target_port` | Unity receiver target. Defaults expect Unity at `192.168.10.2:5005`. |
| `serial_port`, `serial_baud` | Teensy encoder serial connection. |
| `rt_hz` | Main controller loop rate. |
| `output_tmp_dir`, `output_final_dir` | Temporary and final log locations. |

## 4. Change Contexts And Outcomes

The older compact config style uses:

```json
{
  "reward_ms_by_context": {
    "1": 30,
    "2": 0,
    "3": 30
  },
  "airpuff_contexts": [2],
  "airpuff_duration_ms": 50
}
```

For clearer control, prefer an explicit `contexts` list:

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
      "id": 2,
      "scene_id": 2,
      "audio_cue": "context_2",
      "identity_pulses": 2,
      "airpuff_ms": 50
    },
    {
      "id": 3,
      "scene_id": 3,
      "audio_cue": "context_3",
      "identity_pulses": 3,
      "reward_ms": 30
    }
  ]
}
```

Each context needs:

- `id`: context ID used by the controller.
- `scene_id`: scene value sent to Unity during the context zone.
- `audio_cue`: named WAV Trigger cue.
- `identity_pulses`: number of context identity TTL pulses.
- `reward_ms` or `airpuff_ms`: outcome pulse duration. Use `0` or omit for no outcome.

To force an exact trial order, add `context_sequence`. It must contain at least
`num_trials` entries:

```json
{
  "num_trials": 6,
  "context_sequence": [1, 2, 3, 1, 3, 2]
}
```

Without `context_sequence`, contexts are shuffled in blocks using `seed`.

## 5. Change Task Event Actions

Most sessions do not need custom task events. When you do need to change command
order, add `task_events` to the config. These event names are built in:

- `trial_start`
- `context_entry`
- `outcome_start`
- `reward`
- `airpuff`
- `iti_start`

Example: change what happens when entering a context:

```json
{
  "task_events": {
    "context_entry": [
      {"type": "reset_segment"},
      {"type": "teleport"},
      {"type": "start_audio", "cue": "context"},
      {
        "type": "ttl_pulse_train",
        "event": "context_identity",
        "pulse_count": "context_identity"
      },
      {"type": "ttl_pulse", "event": "context_entry"}
    ]
  }
}
```

Available action `type` values:

- `stop_audio`
- `start_audio` with `cue` or `cues`
- `reset_segment`
- `teleport`
- `ttl_pulse` with `event` and optional `duration_ms`
- `ttl_pulse_train` with `event` and `pulse_count`
- `reward` with optional `duration_ms`
- `airpuff` with optional `duration_ms`

Use `"cue": "context"` when the cue should resolve to the current context's
`audio_cue`.

## 6. Change Hardware Pins

Edit `pinmap` in the session JSON. Values are BCM GPIO numbers.

Common defaults:

```json
{
  "pinmap": {
    "water_solenoid": 4,
    "air_solenoid": 5,
    "wav_trial_available": 6,
    "wav_context_1": 7,
    "wav_context_2": 8,
    "wav_context_3": 13,
    "lick_input": 9,
    "ttl_trial_start": 17,
    "ttl_context_identity": 18,
    "ttl_context_entry": 19,
    "ttl_reward": 20,
    "ttl_airpuff": 21,
    "ttl_lick": 22,
    "ttl_iti_start": 23,
    "ttl_outcome_start": 24
  }
}
```

For a new named audio cue, add it under `pinmap.wav_cues`:

```json
{
  "pinmap": {
    "wav_cues": {
      "context_4": 25,
      "tone_overlay": 26
    }
  }
}
```

Every audio cue referenced by `contexts` or `task_events` must have a distinct
pin.

## 7. Run A Safe End-To-End Test

Use mock hardware first. This parses the config, runs the state machine, uses a
synthetic encoder stream, sends mock UDP, writes logs, and exits after the
debugging time limit:

```bash
python -m rpi5_controller.main \
  --config configs/example_session.json \
  --mock-hardware \
  --max-seconds 10
```

Replace `configs/example_session.json` with your generated session file. The
command prints a JSON summary with:

- `trials_completed`
- `duration_s`
- `clock_overruns`
- `dropped_log_entries`
- `log_binary_path`
- `log_metadata_path`

For a fuller software check, run the tests:

```bash
pytest
```

## 8. Test Hardware Lines Before A Real Session

Dry-run the bring-up checklist without hardware effects:

```bash
python tools/hardware_bringup_check.py \
  --config configs/example_session.json \
  --mock-hardware \
  --yes \
  --skip-lick
```

Then run the real hardware checklist:

```bash
python tools/hardware_bringup_check.py --config configs/example_session.json
```

Solenoid pulses are disabled by default in the checklist. Enable them only when
the driver board, tubing, and collection setup are ready:

```bash
python tools/hardware_bringup_check.py \
  --config configs/example_session.json \
  --enable-solenoids
```

## 9. Run The Real Task

Start Unity on the rendering computer and make sure it is listening on the UDP
port from the config. Then run:

```bash
python -m rpi5_controller.main --config configs/your_session.json
```

On the Raspberry Pi with real-time scheduling enabled:

```bash
python -m rpi5_controller.main \
  --config configs/your_session.json \
  --enable-rt \
  --fifo-priority 80 \
  --cpu-core 3
```

Use `--strict-rt` if you want the process to exit instead of warning when
real-time scheduling cannot be applied:

```bash
python -m rpi5_controller.main \
  --config configs/your_session.json \
  --enable-rt \
  --fifo-priority 80 \
  --cpu-core 3 \
  --strict-rt
```

## 10. Where To Look After A Run

By default, live logs are written under `/tmp/bhv_log` and copied to `logs/` on
clean shutdown. The controller prints the final binary and metadata paths at the
end of the run.

The metadata JSON includes the exact config used for the session and the planned
context sequence, which is useful for confirming randomization and reproducing a
test.

## Quick Command Checklist

```bash
source .venv/bin/activate
python tools/configure_session.py
python -m rpi5_controller.main --config configs/your_session.json --mock-hardware --max-seconds 10
pytest
python tools/hardware_bringup_check.py --config configs/your_session.json --mock-hardware --yes --skip-lick
python -m rpi5_controller.main --config configs/your_session.json
```

For deeper task-flow customization examples, see `docs/task_modularity.md`.
