#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ is None or __package__ == "":
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from rpi5_controller.core.config import SessionConfig
from rpi5_controller.hardware.audio import WavTriggerController
from rpi5_controller.hardware.gpio import GPIOBackend, MockGPIOBackend, RPiGPIOBackend


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Play one WAV trigger audio cue for a fixed duration"
    )
    parser.add_argument(
        "context_id",
        type=int,
        nargs="?",
        choices=(1, 2, 3),
        help="Context number to trigger",
    )
    parser.add_argument(
        "--trial-available",
        action="store_true",
        help="Trigger the trial-available cue instead of a context cue",
    )
    parser.add_argument(
        "--config",
        default="configs/example_session.json",
        help="Path to session config JSON (for WAV trigger pin map)",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=1.5,
        help="Trigger duration in seconds",
    )
    parser.add_argument(
        "--mock-hardware",
        action="store_true",
        help="Use mock GPIO backend instead of Raspberry Pi GPIO",
    )
    return parser


def load_config(config_path: str) -> SessionConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return SessionConfig.from_json_file(path)


def build_audio_controller(config: SessionConfig, *, mock_hardware: bool) -> tuple[GPIOBackend, WavTriggerController]:
    gpio: GPIOBackend = MockGPIOBackend() if mock_hardware else RPiGPIOBackend()
    audio = WavTriggerController(
        gpio=gpio,
        trial_available_pin=config.pinmap.wav_trial_available,
        context_pin_map={
            1: config.pinmap.wav_context_1,
            2: config.pinmap.wav_context_2,
            3: config.pinmap.wav_context_3,
        },
    )
    return gpio, audio


def main() -> None:
    args = build_parser().parse_args()
    if args.trial_available and args.context_id is not None:
        raise SystemExit("Choose either a context_id or --trial-available, not both.")
    if not args.trial_available and args.context_id is None:
        raise SystemExit("Provide a context_id or use --trial-available.")

    config = load_config(args.config)
    gpio, audio = build_audio_controller(config, mock_hardware=args.mock_hardware)

    try:
        audio.setup()

        if args.trial_available:
            print(
                f"Playing trial-available on WAV channel 1 "
                f"(BCM pin {audio.trial_available_pin}) for {args.seconds:.1f} s"
            )
            audio.start_trial_available()
        else:
            wav_channel = args.context_id + 1
            bcm_pin = audio.context_pin_map[args.context_id]
            print(
                f"Playing context {args.context_id} on WAV channel {wav_channel} "
                f"(BCM pin {bcm_pin}) for {args.seconds:.1f} s"
            )
            audio.start_context(args.context_id)

        time.sleep(max(0.0, args.seconds))
        audio.stop_all()
    finally:
        gpio.cleanup()

    print("Audio trigger finished.")


if __name__ == "__main__":
    main()
