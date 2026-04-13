#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

if __package__ is None or __package__ == "":
    _repo_root = Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from rpi5_controller.core.config import SessionConfig
from rpi5_controller.hardware.audio import WavTriggerController
from rpi5_controller.hardware.gpio import GPIOBackend, MockGPIOBackend, RPiGPIOBackend
from rpi5_controller.hardware.lick import LickDetector
from rpi5_controller.hardware.pulse import PulseScheduler


@dataclass
class StepResult:
    name: str
    status: str
    detail: str


class HardwareBringUpChecklist:
    def __init__(
        self,
        config: SessionConfig,
        *,
        mock_hardware: bool,
        assume_yes: bool,
        enable_solenoids: bool,
        skip_lick: bool,
        line_test_pulse_ms: int,
        audio_test_seconds: float,
        lick_timeout_s: float,
    ) -> None:
        self.config = config
        self.mock_hardware = mock_hardware
        self.assume_yes = assume_yes
        self.enable_solenoids = enable_solenoids
        self.skip_lick = skip_lick
        self.line_test_pulse_ms = line_test_pulse_ms
        self.audio_test_seconds = audio_test_seconds
        self.lick_timeout_s = lick_timeout_s

        self.results: list[StepResult] = []

        self.gpio: GPIOBackend = MockGPIOBackend() if mock_hardware else RPiGPIOBackend()
        self.scheduler = PulseScheduler(self.gpio)
        self.audio = WavTriggerController(
            gpio=self.gpio,
            trial_available_pin=self.config.pinmap.wav_trial_available,
            context_pin_map={
                1: self.config.pinmap.wav_context_1,
                2: self.config.pinmap.wav_context_2,
                3: self.config.pinmap.wav_context_3,
            },
        )
        self.lick = LickDetector(self.gpio, self.config.pinmap.lick_input)

    def run(self) -> int:
        self._print_header()
        if not self._prompt_yes_no(
            "Confirm no animal is connected and all output loads are safe to actuate",
            default=False,
        ):
            print("Aborted by operator before hardware checks.")
            return 2

        try:
            self._setup_gpio()
            self._run_ttl_checks()
            self._run_audio_checks()
            self._run_solenoid_checks()
            self._run_lick_check()
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            self.results.append(StepResult("Checklist", "FAIL", "Interrupted by user"))
        finally:
            self._cleanup()

        return self._print_summary_and_exit_code()

    def _setup_gpio(self) -> None:
        pinmap = self.config.pinmap

        output_pins = {
            pinmap.water_solenoid,
            pinmap.air_solenoid,
            pinmap.ttl_trial_start,
            pinmap.ttl_context_identity,
            pinmap.ttl_context_entry,
            pinmap.ttl_reward,
            pinmap.ttl_airpuff,
            pinmap.ttl_lick,
            pinmap.ttl_iti_start,
        }

        for pin in output_pins:
            self.gpio.setup_output(pin)
            self.gpio.write(pin, 0)

        self.audio.setup()
        self.lick.setup()

    def _run_ttl_checks(self) -> None:
        print("\n[TTL checks]")
        pinmap = self.config.pinmap

        ttl_single_lines = [
            ("TTL Trial Start (DI0)", pinmap.ttl_trial_start),
            ("TTL Context Entry (DI2)", pinmap.ttl_context_entry),
            ("TTL Reward (DI3)", pinmap.ttl_reward),
            ("TTL Airpuff (DI4)", pinmap.ttl_airpuff),
            ("TTL Lick Onset (DI5)", pinmap.ttl_lick),
            ("TTL ITI Start (DI6)", pinmap.ttl_iti_start),
        ]

        for name, pin in ttl_single_lines:
            self._pulse_and_confirm(
                step_name=name,
                pin=pin,
                duration_ms=self.line_test_pulse_ms,
                confirmation_prompt=f"Observed {name} pulse on NI/scope?",
            )

        print("Testing context identity pulse train on DI1 (1, 2, 3 pulses).")
        for pulse_count in (1, 2, 3):
            now_s = time.monotonic()
            self.scheduler.schedule_pulse_train(
                pin=pinmap.ttl_context_identity,
                pulses=pulse_count,
                pulse_width_ms=self.config.ttl_pulse_width_ms,
                gap_ms=self.config.ttl_train_gap_ms,
                now_s=now_s,
            )
            total_ms = (
                pulse_count * self.config.ttl_pulse_width_ms
                + max(0, pulse_count - 1) * self.config.ttl_train_gap_ms
            )
            self._service_scheduler_for((total_ms / 1000.0) + 0.05)

            observed = self._prompt_yes_no(
                f"Observed context identity train with {pulse_count} pulses on DI1?",
                default=True,
            )
            self._record(
                name=f"TTL Context Identity ({pulse_count} pulses)",
                status="PASS" if observed else "FAIL",
                detail=(
                    f"BCM {pinmap.ttl_context_identity}, width={self.config.ttl_pulse_width_ms} ms, "
                    f"gap={self.config.ttl_train_gap_ms} ms"
                ),
            )

    def _run_audio_checks(self) -> None:
        print("\n[Audio trigger checks]")
        print(
            f"Triggering WAV trial-available cue (BCM pin {self.audio.trial_available_pin}) "
            f"for {self.audio_test_seconds:.1f} s"
        )
        self.audio.start_trial_available()
        time.sleep(self.audio_test_seconds)
        self.audio.stop_all()

        observed = self._prompt_yes_no(
            "Did the trial-available audio trigger on WAV channel 1 and stop as expected?",
            default=True,
        )
        self._record(
            name="Audio Trial Available",
            status="PASS" if observed else "FAIL",
            detail=f"WAV channel 1, BCM {self.audio.trial_available_pin}",
        )

        for context_id in (1, 2, 3):
            wav_channel = context_id + 1
            print(
                f"Triggering WAV context {context_id} cue on channel {wav_channel} "
                f"(BCM pin {self.audio.context_pin_map[context_id]}) "
                f"for {self.audio_test_seconds:.1f} s"
            )
            self.audio.start_context(context_id)
            time.sleep(self.audio_test_seconds)
            self.audio.stop_all()

            observed = self._prompt_yes_no(
                f"Did context {context_id} audio trigger on WAV channel {wav_channel} "
                "and stop as expected?",
                default=True,
            )
            self._record(
                name=f"Audio Context {context_id}",
                status="PASS" if observed else "FAIL",
                detail=(
                    f"WAV channel {wav_channel}, BCM {self.audio.context_pin_map[context_id]}"
                ),
            )

    def _run_solenoid_checks(self) -> None:
        print("\n[Solenoid checks]")
        pinmap = self.config.pinmap

        if not self.enable_solenoids:
            self._record(
                name="Water solenoid",
                status="SKIP",
                detail="Skipped (use --enable-solenoids to actuate)",
            )
            self._record(
                name="Air solenoid",
                status="SKIP",
                detail="Skipped (use --enable-solenoids to actuate)",
            )
            return

        reward_duration_ms = max(self.config.reward_ms_by_context.values())
        reward_duration_ms = reward_duration_ms if reward_duration_ms > 0 else 30

        self._pulse_and_confirm(
            step_name="Water solenoid",
            pin=pinmap.water_solenoid,
            duration_ms=reward_duration_ms,
            confirmation_prompt=(
                f"Observed water solenoid actuation (duration {reward_duration_ms} ms)?"
            ),
        )

        self._pulse_and_confirm(
            step_name="Air solenoid",
            pin=pinmap.air_solenoid,
            duration_ms=self.config.airpuff_duration_ms,
            confirmation_prompt=(
                f"Observed air solenoid actuation (duration {self.config.airpuff_duration_ms} ms)?"
            ),
        )

    def _run_lick_check(self) -> None:
        print("\n[Lick detector check]")
        if self.skip_lick:
            self._record("Lick detector", "SKIP", "Skipped by --skip-lick")
            return

        if self.mock_hardware:
            if isinstance(self.gpio, MockGPIOBackend):
                pin = self.config.pinmap.lick_input
                self.gpio.set_input_value(pin, 0)
                self.lick.sample()
                self.gpio.set_input_value(pin, 1)
                _, onset, _ = self.lick.sample()
                self.gpio.set_input_value(pin, 0)
                self.lick.sample()
                self._record(
                    "Lick detector",
                    "PASS" if onset else "FAIL",
                    "Mock rising-edge simulation",
                )
            else:
                self._record("Lick detector", "FAIL", "Mock mode requested but backend mismatch")
            return

        print(
            f"Touch the lick spout now. Listening for rising edges for {self.lick_timeout_s:.1f} s..."
        )
        deadline = time.monotonic() + self.lick_timeout_s
        onsets = 0
        while time.monotonic() < deadline:
            _, onset, _ = self.lick.sample()
            if onset:
                onsets += 1
                print(f"Detected lick onset #{onsets}")
            time.sleep(0.002)

        if onsets > 0:
            self._record("Lick detector", "PASS", f"Detected {onsets} onset(s)")
            return

        observed = self._prompt_yes_no(
            "No lick onsets detected. Mark lick check as pass anyway?",
            default=False,
        )
        self._record(
            "Lick detector",
            "PASS" if observed else "FAIL",
            "No onsets detected in timeout window",
        )

    def _pulse_and_confirm(
        self,
        *,
        step_name: str,
        pin: int,
        duration_ms: int,
        confirmation_prompt: str,
    ) -> None:
        print(f"Pulsing {step_name} on BCM {pin} for {duration_ms} ms")
        now_s = time.monotonic()
        self.scheduler.schedule_pulse(pin=pin, duration_ms=duration_ms, now_s=now_s)
        self._service_scheduler_for((duration_ms / 1000.0) + 0.05)

        observed = self._prompt_yes_no(confirmation_prompt, default=True)
        self._record(
            name=step_name,
            status="PASS" if observed else "FAIL",
            detail=f"BCM {pin}, pulse={duration_ms} ms",
        )

    def _service_scheduler_for(self, duration_s: float) -> None:
        deadline = time.monotonic() + max(0.0, duration_s)
        while time.monotonic() < deadline:
            self.scheduler.update(time.monotonic())
            time.sleep(0.001)
        self.scheduler.update(time.monotonic())

    def _record(self, name: str, status: str, detail: str) -> None:
        self.results.append(StepResult(name=name, status=status, detail=detail))

    def _print_header(self) -> None:
        print("RPi5 Hardware Bring-Up Checklist")
        print("--------------------------------")
        print(f"Session config animal_id: {self.config.animal_id}")
        print(f"Mock hardware mode: {self.mock_hardware}")

    def _cleanup(self) -> None:
        try:
            self.audio.stop_all()
        finally:
            self.gpio.cleanup()

    def _print_summary_and_exit_code(self) -> int:
        print("\nSummary")
        print("-------")
        for result in self.results:
            print(f"[{result.status:<4}] {result.name}: {result.detail}")

        fail_count = sum(1 for result in self.results if result.status == "FAIL")
        skip_count = sum(1 for result in self.results if result.status == "SKIP")
        pass_count = sum(1 for result in self.results if result.status == "PASS")

        print(
            f"\nTotals: PASS={pass_count}, FAIL={fail_count}, SKIP={skip_count}, "
            f"ALL={len(self.results)}"
        )

        if fail_count > 0:
            return 1
        return 0

    def _prompt_yes_no(self, question: str, *, default: bool) -> bool:
        if self.assume_yes:
            print(f"{question} -> yes (--yes)")
            return True

        suffix = "Y/n" if default else "y/N"
        while True:
            answer = input(f"{question} [{suffix}]: ").strip().lower()
            if answer == "":
                return default
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hardware bring-up checklist for RPi5 VR task")
    parser.add_argument(
        "--config",
        default="configs/example_session.json",
        help="Path to session config JSON (for pin map and pulse settings)",
    )
    parser.add_argument(
        "--mock-hardware",
        action="store_true",
        help="Use mock GPIO backend (safe dry-run)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Automatically answer yes to confirmation prompts",
    )
    parser.add_argument(
        "--enable-solenoids",
        action="store_true",
        help="Allow water/air solenoid pulses (disabled by default for safety)",
    )
    parser.add_argument(
        "--skip-lick",
        action="store_true",
        help="Skip lick detector check",
    )
    parser.add_argument(
        "--line-test-pulse-ms",
        type=int,
        default=5,
        help="Pulse width for TTL single-line checks",
    )
    parser.add_argument(
        "--audio-test-seconds",
        type=float,
        default=1.5,
        help="Duration for each context audio trigger test",
    )
    parser.add_argument(
        "--lick-timeout-s",
        type=float,
        default=10.0,
        help="Timeout window for lick detection",
    )
    return parser


def load_config(config_path: str) -> SessionConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return SessionConfig.from_json_file(path)


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)

    checklist = HardwareBringUpChecklist(
        config,
        mock_hardware=args.mock_hardware,
        assume_yes=args.yes,
        enable_solenoids=args.enable_solenoids,
        skip_lick=args.skip_lick,
        line_test_pulse_ms=args.line_test_pulse_ms,
        audio_test_seconds=args.audio_test_seconds,
        lick_timeout_s=args.lick_timeout_s,
    )
    code = checklist.run()
    sys.exit(code)


if __name__ == "__main__":
    main()
