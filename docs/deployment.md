# Deployment Runbook (RPi5)

## 1. OS and Kernel

- Install Raspberry Pi OS with PREEMPT_RT kernel.
- Validate jitter target with `cyclictest` before experiments.

## 2. CPU Isolation and Priority

- Add `isolcpus=3` to `/boot/cmdline.txt`.
- Launch controller pinned to isolated core:
  - `taskset -c 3 chrt -f 80 python -m rpi5_controller.main --config <config.json>`

## 3. Network

- Direct Ethernet cable between RPi5 and Unity PC.
- Static IPs:
  - RPi5: `192.168.10.1`
  - Unity: `192.168.10.2`
- UDP target port: `5005`

## 4. Logs

- In-loop logging writes to tmpfs path from config (`output_tmp_dir`, default `/tmp/bhv_log`).
- On clean shutdown, artifacts are copied to `output_final_dir`.

## 5. Session Launch

1. Run `python tools/configure_session.py`
2. Confirm generated JSON
3. Launch main controller command from the script output

## 6. Safety Checks

- Solenoids must be driven via a transistor/MOSFET driver board.
- Verify NI TTL input threshold for 3.3V logic or use level shifter.
- Do not connect inductive loads directly to RPi GPIO.
