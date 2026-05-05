from __future__ import annotations

import argparse
import math
import sys
import time

from rpi5_controller.core.config import SessionConfig
from rpi5_controller.hardware.serial_uart import SerialEncoderReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure Teensy encoder counts per physical wheel revolution."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to session JSON config with serial and wheel settings",
    )
    parser.add_argument(
        "--revolutions",
        type=float,
        default=1.0,
        help="Number of full wheel revolutions to rotate during calibration",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=2.0,
        help="Seconds to wait for an encoder packet after each prompt",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.revolutions <= 0:
        raise SystemExit("--revolutions must be > 0")

    config = SessionConfig.from_json_file(args.config)
    circumference_cm = math.pi * config.wheel_diameter_cm

    print(
        f"Wheel diameter: {config.wheel_diameter_cm:.3f} cm "
        f"(circumference {circumference_cm:.3f} cm)"
    )
    print(f"Current config encoder_cpr: {config.encoder_cpr}")
    print(f"Serial: {config.serial_port} at {config.serial_baud} baud")
    print()

    reader = SerialEncoderReader(
        port=config.serial_port,
        baudrate=config.serial_baud,
    )
    try:
        input("Put a marker at the start position, then press Enter...")
        start_count = _read_adjusted_count(reader, config, timeout_s=args.timeout_s)

        input(
            f"Rotate the wheel forward exactly {args.revolutions:g} full "
            "revolution(s), stop on the marker, then press Enter..."
        )
        end_count = _read_adjusted_count(reader, config, timeout_s=args.timeout_s)
    finally:
        reader.close()

    delta_counts = _signed_count_delta(
        current_count=end_count,
        previous_count=start_count,
    )
    counts_per_revolution = abs(delta_counts) / args.revolutions
    if counts_per_revolution == 0:
        raise SystemExit(
            "No encoder movement was detected. The quadrature firmware expects "
            "sensor channel A on Teensy pin 2 and sensor channel B on Teensy "
            "pin 3. Do not use the I/index line as channel B."
        )

    suggested_cpr = int(round(counts_per_revolution))
    print()
    print(f"Start adjusted count: {start_count}")
    print(f"End adjusted count:   {end_count}")
    print(f"Signed count delta:   {delta_counts}")
    print(f"Measured counts/rev:  {counts_per_revolution:.3f}")
    print()
    print("Suggested session config change:")
    print(f'  "wheel_diameter_cm": {config.wheel_diameter_cm:.3f},')
    print(f'  "encoder_cpr": {suggested_cpr}')
    print()
    print(
        "With that calibration, one full wheel revolution maps to "
        f"{circumference_cm:.3f} cm."
    )


def _read_adjusted_count(
    reader: SerialEncoderReader,
    config: SessionConfig,
    *,
    timeout_s: float,
) -> int:
    deadline_s = time.monotonic() + timeout_s
    latest_count: int | None = None
    while time.monotonic() < deadline_s:
        packet = reader.read_latest_packet()
        if packet is not None:
            latest_count = _normalize_count(
                -packet.encoder_count if config.invert_encoder else packet.encoder_count
            )
        if latest_count is not None:
            return latest_count
        time.sleep(0.01)

    raise SystemExit(
        "No encoder packets received. Check Teensy power, UART wiring, serial_port, "
        "and serial_baud."
    )


def _normalize_count(count: int) -> int:
    return (count + 0x8000) % 0x10000 - 0x8000


def _signed_count_delta(*, current_count: int, previous_count: int) -> int:
    return (current_count - previous_count + 0x8000) % 0x10000 - 0x8000


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCalibration aborted.", file=sys.stderr)
        raise SystemExit(130)
