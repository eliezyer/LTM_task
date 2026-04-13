# Hardware Bring-Up Checklist Script

Use this script before first animal sessions to validate digital outputs and input wiring.

- Script: `/Users/elie/Documents/github/LTM_task/tools/hardware_bringup_check.py`

## What It Checks

- TTL single pulses (DI0, DI2, DI3, DI4, DI5, DI6)
- Context identity pulse trains on DI1 (1, 2, 3 pulses)
- WAV Trigger trial-available line (channel 1) plus context lines (channels 2, 3, 4)
- Optional solenoid actuation (water + air)
- Lick detector rising-edge detection

## Safe Dry Run (No Hardware)

```bash
python /Users/elie/Documents/github/LTM_task/tools/hardware_bringup_check.py \
  --config /Users/elie/Documents/github/LTM_task/configs/example_session.json \
  --mock-hardware \
  --yes \
  --skip-lick
```

## Real Hardware Run

```bash
python /Users/elie/Documents/github/LTM_task/tools/hardware_bringup_check.py \
  --config /Users/elie/Documents/github/LTM_task/configs/example_session.json
```

## Enable Solenoid Pulses

Solenoids are skipped by default for safety. Enable explicitly:

```bash
python /Users/elie/Documents/github/LTM_task/tools/hardware_bringup_check.py \
  --config /Users/elie/Documents/github/LTM_task/configs/example_session.json \
  --enable-solenoids
```

## Exit Codes

- `0`: all executed checks passed
- `1`: one or more checks failed
- `2`: aborted before execution
