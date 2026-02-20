# RPi5 VR Behavioral Task Controller

Complete implementation of the head-fixed mouse VR behavioral task described in the provided technical specification.

## Contents

- `rpi5_controller/`: Real-time controller package for Raspberry Pi 5
- `tools/configure_session.py`: Interactive session configuration UI
- `teensy_firmware/teensy_encoder_streamer.ino`: Teensy 4.1 encoder UART firmware
- `docs/`: Deployment, wiring, and operations documentation
- `configs/`: Session JSON outputs and examples

## Quick Start

1. Create a Python environment and install test dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e .[dev]`
2. Generate a session config:
   - `python tools/configure_session.py`
3. Run the controller:
   - `python -m rpi5_controller.main --config configs/<session_file>.json`
4. Dry-run with no hardware:
   - `python -m rpi5_controller.main --config configs/<session_file>.json --mock-hardware`

## Testing

- `pytest`

## Notes

- Real-time scheduling (`SCHED_FIFO`, CPU affinity, PREEMPT_RT kernel tuning) is documented in `docs/deployment.md`.
- GPIO defaults follow the spec and can be overridden in the JSON config.
