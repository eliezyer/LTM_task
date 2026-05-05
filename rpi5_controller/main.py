from __future__ import annotations

import argparse
import json
import os
import sys

from rpi5_controller.core.config import SessionConfig
from rpi5_controller.runtime.session_runner import BehaviorSessionRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run RPi5 VR behavioral task session")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to session JSON config",
    )
    parser.add_argument(
        "--mock-hardware",
        action="store_true",
        help="Use mock GPIO/UART/UDP for dry runs",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Optional hard stop for debugging",
    )
    parser.add_argument(
        "--enable-rt",
        action="store_true",
        help="Enable SCHED_FIFO and optional CPU affinity before starting loop",
    )
    parser.add_argument(
        "--fifo-priority",
        type=int,
        default=80,
        help="SCHED_FIFO priority used when --enable-rt is set",
    )
    parser.add_argument(
        "--cpu-core",
        type=int,
        default=None,
        help="Optional CPU core pinning target when --enable-rt is set",
    )
    parser.add_argument(
        "--strict-rt",
        action="store_true",
        help="Exit if real-time scheduling cannot be applied",
    )
    return parser


def configure_realtime(
    *,
    priority: int,
    cpu_core: int | None,
) -> None:
    if cpu_core is not None:
        os.sched_setaffinity(0, {cpu_core})

    os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(priority))


def main() -> None:
    args = build_parser().parse_args()
    if args.enable_rt:
        try:
            configure_realtime(priority=args.fifo_priority, cpu_core=args.cpu_core)
        except Exception as exc:
            if args.strict_rt:
                raise
            print(
                f"[warning] failed to apply RT scheduling: {exc}",
                file=sys.stderr,
            )

    config = SessionConfig.from_json_file(args.config)

    runner = BehaviorSessionRunner(
        config,
        use_mock_hardware=args.mock_hardware,
        max_seconds=args.max_seconds,
    )
    result = runner.run()

    print(
        json.dumps(
            {
                "session_tag": result.session_tag,
                "trials_completed": result.trials_completed,
                "total_ticks": result.total_ticks,
                "duration_s": round(result.duration_s, 3),
                "stop_reason": result.stop_reason,
                "clock_overruns": result.clock_overruns,
                "dropped_log_entries": result.dropped_log_entries,
                "log_binary_path": str(result.log_binary_path),
                "event_log_path": str(result.event_log_path),
                "log_metadata_path": str(result.log_metadata_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
