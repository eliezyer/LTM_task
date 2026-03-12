#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if __package__ is None or __package__ == "":
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from rpi5_controller.core.config import SessionConfig, write_session_config
from rpi5_controller.core.enums import SessionType


def prompt_str(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default


def prompt_int(prompt: str, default: int) -> int:
    while True:
        raw = prompt_str(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("Enter a valid integer.")


def prompt_float(prompt: str, default: float) -> float:
    while True:
        raw = prompt_str(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print("Enter a valid number.")


def prompt_yes_no(prompt: str, default: bool = False) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{default_label}]: ").strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        if raw == "":
            return default


def prompt_session_type() -> SessionType:
    options = [
        SessionType.TRAINING,
        SessionType.RETRIEVAL,
        SessionType.RETRAINING,
    ]
    print("Session type:")
    for idx, option in enumerate(options, start=1):
        print(f"  {idx}. {option.value}")

    while True:
        choice = prompt_str("Select session type", "1")
        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        if choice in {opt.value for opt in options}:
            return SessionType(choice)
        print("Select 1, 2, 3 or type the session name.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create session config for VR behavioral task")
    parser.add_argument(
        "--output-dir",
        default="configs",
        help="Directory for generated config JSON",
    )
    parser.add_argument(
        "--auto-launch",
        action="store_true",
        help="Launch task immediately after confirmation",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    print("RPi5 VR Behavioral Task Session Configuration")
    print("---------------------------------------------")

    animal_id = prompt_str("Animal ID")
    session_type = prompt_session_type()
    num_trials = prompt_int("Number of trials", 50)

    reward_ms_by_context = {
        1: prompt_int("Reward pulse duration context 1 (ms)", 30),
        2: prompt_int("Reward pulse duration context 2 (ms)", 0),
        3: prompt_int("Reward pulse duration context 3 (ms)", 30),
    }

    airpuff_contexts: list[int] = []
    for context_id in (1, 2, 3):
        if prompt_yes_no(f"Deliver airpuff in context {context_id}?", default=False):
            airpuff_contexts.append(context_id)

    airpuff_duration_ms = prompt_int("Airpuff pulse duration (ms)", 50)

    iti_kind = prompt_str("ITI distribution kind (uniform or truncated_exponential)", "uniform")
    iti_min = prompt_float("ITI min (seconds)", 2.0)
    iti_max = prompt_float("ITI max (seconds)", 4.0)
    iti_mean = prompt_float("ITI mean (seconds)", 3.0)

    speed_threshold = prompt_float("Speed threshold for initiation (cm/s)", 1.0)
    stall_timeout = prompt_float("Stall timeout (seconds)", 3.0)

    opening_length = prompt_float("Opening corridor length (cm)", 60.0)
    context_length = prompt_float("Context zone length (cm)", 120.0)
    reward_zone = prompt_float("Reward zone position inside context zone (cm)", 100.0)

    wheel_diameter = prompt_float("Wheel diameter (cm)", 20.0)
    encoder_cpr = prompt_int("Encoder CPR", 1024)
    speed_alpha = prompt_float("Speed EMA alpha", 0.2)

    output_tmp_dir = prompt_str("Temporary log dir", "/tmp/bhv_log")
    output_final_dir = prompt_str("Final log dir", "logs")

    seed_raw = prompt_str("Context randomization seed (blank for system random)", "")
    seed = int(seed_raw) if seed_raw else None

    config_payload = {
        "animal_id": animal_id,
        "session_type": session_type.value,
        "num_trials": num_trials,
        "reward_ms_by_context": reward_ms_by_context,
        "airpuff_contexts": airpuff_contexts,
        "airpuff_duration_ms": airpuff_duration_ms,
        "iti_distribution": {
            "kind": iti_kind,
            "min_s": iti_min,
            "max_s": iti_max,
            "mean_s": iti_mean,
        },
        "speed_threshold_cm_s": speed_threshold,
        "stall_timeout_s": stall_timeout,
        "opening_corridor_length_cm": opening_length,
        "context_zone_length_cm": context_length,
        "reward_zone_position_cm": reward_zone,
        "wheel_diameter_cm": wheel_diameter,
        "encoder_cpr": encoder_cpr,
        "speed_alpha": speed_alpha,
        "output_tmp_dir": output_tmp_dir,
        "output_final_dir": output_final_dir,
        "seed": seed,
    }

    config = SessionConfig.from_dict(config_payload)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"session_{config.animal_id}_{timestamp}.json"
    write_session_config(out_path, config)

    print("\nConfig generated:")
    print(out_path)
    print(json.dumps(config.to_json_dict(), indent=2, sort_keys=True))

    if not prompt_yes_no("Confirm configuration and continue", default=True):
        print("Aborted before launch.")
        return

    if args.auto_launch and prompt_yes_no("Launch behavioral process now", default=True):
        use_mock = prompt_yes_no("Launch with mock hardware", default=False)
        cmd = [sys.executable, "-m", "rpi5_controller.main", "--config", str(out_path)]
        if use_mock:
            cmd.append("--mock-hardware")
        print("Executing:")
        print(" ".join(cmd))
        subprocess.run(cmd, check=True)
    else:
        print("Launch command:")
        print(f"{sys.executable} -m rpi5_controller.main --config {out_path}")


if __name__ == "__main__":
    main()
