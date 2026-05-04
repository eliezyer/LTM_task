from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rpi5_controller.core.commands import Command, CommandType
from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.enums import BehaviorState, SessionType, UdpFlags
from rpi5_controller.core.packets import UdpPositionPacket
from rpi5_controller.core.position import PositionDecoder, SpeedEstimator
from rpi5_controller.core.state_machine import BehaviorStateMachine, TickInput
from rpi5_controller.hardware.audio import WavTriggerController
from rpi5_controller.hardware.executor import HardwareCommandExecutor
from rpi5_controller.hardware.gpio import MockGPIOBackend, RPiGPIOBackend
from rpi5_controller.hardware.lick import LickDetector
from rpi5_controller.hardware.pulse import PulseScheduler
from rpi5_controller.hardware.serial_uart import (
    EncoderReader,
    SerialEncoderReader,
    SyntheticEncoderReader,
)
from rpi5_controller.hardware.udp import MockUdpSender, UdpSender
from rpi5_controller.logging.log_entry import LogEntry
from rpi5_controller.logging.ring_buffer import ThreadSafeRingBuffer
from rpi5_controller.logging.writer import (
    AsyncLogWriter,
    build_log_paths,
    finalize_log_artifacts,
)
from rpi5_controller.logging.trial_events import TrialEventLogger
from rpi5_controller.runtime.clock import RealtimeTicker


@dataclass(frozen=True)
class SessionResult:
    session_tag: str
    total_ticks: int
    duration_s: float
    trials_completed: int
    dropped_log_entries: int
    clock_overruns: int
    log_binary_path: Path
    log_metadata_path: Path
    event_log_path: Path


class BehaviorSessionRunner:
    def __init__(
        self,
        config: SessionConfig,
        *,
        use_mock_hardware: bool = False,
        max_seconds: float | None = None,
    ):
        self.config = config
        self.use_mock_hardware = use_mock_hardware
        self.max_seconds = max_seconds

        self.state_machine = BehaviorStateMachine(config)
        self.position_decoder = PositionDecoder(
            wheel_diameter_cm=config.wheel_diameter_cm,
            encoder_cpr=config.encoder_cpr,
        )
        self.speed_estimator = SpeedEstimator(
            wheel_diameter_cm=config.wheel_diameter_cm,
            encoder_cpr=config.encoder_cpr,
            alpha=config.speed_alpha,
        )
        self.ticker = RealtimeTicker(config.rt_hz)

        self._seq_num = 0
        self._tick_counter = 0
        self._encoder_count = 0
        self._raw_encoder_count: int | None = None
        self._packets_received = 0
        self._last_packet_monotonic_s: float | None = None
        self._last_packet_timestamp_ms: int | None = None
        self._last_status_log_s: float | None = None
        self._last_status_encoder_count: int | None = None

        self._gpio = MockGPIOBackend() if use_mock_hardware else RPiGPIOBackend()
        self._encoder_reader = self._build_encoder_reader()
        self._udp_sender = MockUdpSender() if use_mock_hardware else UdpSender(
            config.udp_target_ip,
            config.udp_target_port,
        )

        self._audio = WavTriggerController(
            gpio=self._gpio,
            trial_available_pin=config.pinmap.wav_trial_available,
            context_pin_map=config.context_audio_pin_map,
            cue_pin_map=config.audio_cue_pin_map,
            context_cue_map=config.context_audio_cue_map,
        )
        self._pulse_scheduler = PulseScheduler(self._gpio)
        self._executor = HardwareCommandExecutor(
            config=config,
            gpio=self._gpio,
            pulse_scheduler=self._pulse_scheduler,
            audio=self._audio,
        )
        self._lick = LickDetector(self._gpio, config.pinmap.lick_input)

        self._log_buffer: ThreadSafeRingBuffer[LogEntry] = ThreadSafeRingBuffer(maxlen=250_000)
        self._log_writer: AsyncLogWriter | None = None
        self._event_logger: TrialEventLogger | None = None

    def run(self) -> SessionResult:
        session_tag = self._build_session_tag()
        log_paths = build_log_paths(
            tmp_dir=self.config.output_tmp_dir,
            final_dir=self.config.output_final_dir,
            session_tag=session_tag,
        )
        metadata = self._build_metadata(session_tag)

        self._executor.setup()
        self._lick.setup()

        self._log_writer = AsyncLogWriter(self._log_buffer, log_paths.tmp_binary_path)
        self._log_writer.start()
        AsyncLogWriter.write_metadata(log_paths.tmp_metadata_path, metadata)
        self._event_logger = TrialEventLogger(log_paths.tmp_event_path)
        self._event_logger.start()

        start_now_s = self.ticker.monotonic_s()
        session_start_s = start_now_s
        self._last_status_log_s = session_start_s
        self._last_status_encoder_count = self._encoder_count
        started = self.state_machine.start_session(start_now_s)
        self._process_commands(started.commands, start_now_s)
        self._log_task_event(
            "session_start",
            now_s=start_now_s,
            session_start_s=session_start_s,
            tick_out=started,
            segment_position_cm=self.position_decoder.segment_position_cm(
                self._encoder_count
            ),
            speed_cm_s=0.0,
            commands=started.commands,
        )
        self._log_task_event(
            "trial_start",
            now_s=start_now_s,
            session_start_s=session_start_s,
            tick_out=started,
            segment_position_cm=self.position_decoder.segment_position_cm(
                self._encoder_count
            ),
            speed_cm_s=0.0,
            commands=started.commands,
        )

        # Broadcast initial scene state immediately before entering periodic loop.
        self._send_udp(
            position_cm=self.position_decoder.segment_position_cm(self._encoder_count),
            scene_id=started.scene_id,
            flags=started.flags,
        )

        start_monotonic_s = self.ticker.monotonic_s()
        self.ticker.start()
        stop_reason = "unknown"

        try:
            while True:
                now_s = self.ticker.monotonic_s()
                elapsed_s = now_s - start_monotonic_s
                if self.max_seconds is not None and elapsed_s >= self.max_seconds:
                    stop_reason = "max_seconds"
                    break

                self._read_latest_encoder_packet(now_s)

                segment_position_cm = self.position_decoder.segment_position_cm(
                    self._encoder_count
                )
                speed_cm_s = self.speed_estimator.update(self._encoder_count, now_s)
                lick_level, lick_onset, _ = self._lick.sample()

                prev_state = self.state_machine.state
                prev_trial_index = self.state_machine.current_trial_index
                prev_context_id = self.state_machine.current_context

                tick_out = self.state_machine.tick(
                    TickInput(
                        now_s=now_s,
                        segment_position_cm=segment_position_cm,
                        speed_cm_s=speed_cm_s,
                        lick_onset=lick_onset,
                    )
                )
                exec_result = self._process_commands(tick_out.commands, now_s)
                self._log_state_transition_events(
                    previous_state=prev_state,
                    previous_trial_index=prev_trial_index,
                    previous_context_id=prev_context_id,
                    now_s=now_s,
                    session_start_s=session_start_s,
                    tick_out=tick_out,
                    segment_position_cm=segment_position_cm,
                    speed_cm_s=speed_cm_s,
                    commands=tick_out.commands,
                )

                segment_position_cm = self.position_decoder.segment_position_cm(
                    self._encoder_count
                )
                self._executor.update(now_s)

                self._send_udp(
                    position_cm=segment_position_cm,
                    scene_id=tick_out.scene_id,
                    flags=tick_out.flags,
                )

                tick_ms = int(elapsed_s * 1000.0)
                log_entry = LogEntry(
                    tick_ms=tick_ms,
                    encoder_count=self._encoder_count,
                    virtual_pos_cm=segment_position_cm,
                    state=int(tick_out.state),
                    context_id=tick_out.context_id,
                    lick=lick_level,
                    reward_on=int(tick_out.reward_on or exec_result.reward_on),
                    airpuff_on=int(tick_out.airpuff_on or exec_result.airpuff_on),
                    flags=int(tick_out.flags),
                )
                self._log_buffer.push(log_entry)

                self._tick_counter += 1
                self._log_status_if_due(
                    now_s=now_s,
                    session_start_s=session_start_s,
                    tick_out=tick_out,
                    segment_position_cm=segment_position_cm,
                    speed_cm_s=speed_cm_s,
                )
                if self.state_machine.session_complete:
                    stop_reason = "session_complete"
                    break

                self.ticker.wait_next()
        finally:
            self._log_session_stop(
                reason=stop_reason,
                now_s=self.ticker.monotonic_s(),
                session_start_s=session_start_s,
            )
            self._shutdown(log_paths)

        duration_s = self.ticker.monotonic_s() - start_monotonic_s
        return SessionResult(
            session_tag=session_tag,
            total_ticks=self._tick_counter,
            duration_s=duration_s,
            trials_completed=self.state_machine.trials_completed,
            dropped_log_entries=self._log_buffer.dropped_items,
            clock_overruns=self.ticker.overrun_count,
            log_binary_path=log_paths.final_binary_path,
            log_metadata_path=log_paths.final_metadata_path,
            event_log_path=log_paths.final_event_path,
        )

    def _process_commands(self, commands: list[Command], now_s: float):
        hw_commands: list[Command] = []
        for cmd in commands:
            if cmd.type == CommandType.RESET_SEGMENT:
                self.position_decoder.reset_segment(self._encoder_count)
            elif cmd.type == CommandType.TELEPORT:
                continue
            else:
                hw_commands.append(cmd)
        return self._executor.execute(hw_commands, now_s)

    def _read_latest_encoder_packet(self, now_s: float) -> None:
        packet = self._encoder_reader.read_latest_packet()
        if packet is None:
            return

        self._raw_encoder_count = packet.encoder_count
        adjusted_count = (
            -packet.encoder_count if self.config.invert_encoder else packet.encoder_count
        )
        self._encoder_count = self._normalize_encoder_count(adjusted_count)
        self._packets_received += 1
        self._last_packet_monotonic_s = now_s
        self._last_packet_timestamp_ms = packet.timestamp_ms

    @staticmethod
    def _normalize_encoder_count(count: int) -> int:
        return (count + 0x8000) % 0x10000 - 0x8000

    def _log_status_if_due(
        self,
        *,
        now_s: float,
        session_start_s: float,
        tick_out,
        segment_position_cm: float,
        speed_cm_s: float,
    ) -> None:
        if self._last_status_log_s is None:
            self._last_status_log_s = now_s
            self._last_status_encoder_count = self._encoder_count
            return

        if now_s - self._last_status_log_s < self.config.task_status_interval_s:
            return

        reason = None
        if self._packets_received == 0:
            reason = "no_encoder_packets"
        elif (
            self._last_status_encoder_count is not None
            and self._encoder_count == self._last_status_encoder_count
        ):
            reason = "no_encoder_delta_since_last_status"
        elif segment_position_cm < 0:
            reason = "negative_position_check_invert_encoder"

        self._log_task_event(
            "status",
            now_s=now_s,
            session_start_s=session_start_s,
            tick_out=tick_out,
            segment_position_cm=segment_position_cm,
            speed_cm_s=speed_cm_s,
            commands=[],
            reason=reason,
        )
        self._last_status_log_s = now_s
        self._last_status_encoder_count = self._encoder_count

    def _send_udp(self, position_cm: float, scene_id: int, flags: UdpFlags) -> None:
        packet = UdpPositionPacket(
            seq_num=self._seq_num,
            position_cm=position_cm,
            scene_id=scene_id,
            flags=flags,
        )
        self._udp_sender.send(packet)
        self._seq_num = (self._seq_num + 1) & 0xFFFFFFFF

    def _build_session_tag(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.config.animal_id}_{self.config.session_type.value}_{timestamp}"

    def _build_metadata(self, session_tag: str) -> dict[str, Any]:
        return {
            "session_tag": session_tag,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "animal_id": self.config.animal_id,
            "session_type": self.config.session_type.value,
            "context_sequence": self.state_machine.planned_context_sequence,
            "config": self.config.to_json_dict(),
        }

    def _log_state_transition_events(
        self,
        *,
        previous_state: BehaviorState,
        previous_trial_index: int,
        previous_context_id: int,
        now_s: float,
        session_start_s: float,
        tick_out,
        segment_position_cm: float,
        speed_cm_s: float,
        commands: list[Command],
    ) -> None:
        current_state = tick_out.state
        if current_state == previous_state:
            return

        if previous_state == BehaviorState.OPENING_CORRIDOR and current_state == BehaviorState.CONTEXT_ZONE:
            self._log_task_event(
                "context_entry",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
            )
            return

        if previous_state == BehaviorState.CONTEXT_ZONE and current_state == BehaviorState.OUTCOME_ZONE:
            self._log_task_event(
                "outcome_start",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
                reason="reward_zone_reached",
            )
            return

        if previous_state == BehaviorState.CONTEXT_ZONE and current_state == BehaviorState.ITI:
            reason = "reward_zone_reached"
            if segment_position_cm < self.config.reward_zone_position_cm:
                reason = "stall_timeout"
            elif self.config.session_type == SessionType.RETRIEVAL:
                reason = "retrieval_suppressed_outcome"
            elif not self._context_expected_outcome(previous_context_id)["events"]:
                reason = "no_context_outcome"
            self._log_task_event(
                "iti_start",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
                reason=reason,
            )
            return

        if previous_state == BehaviorState.OUTCOME_ZONE and current_state == BehaviorState.ITI:
            self._log_task_event(
                "iti_start",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
                reason="outcome_complete",
            )
            return

        if previous_state == BehaviorState.ITI and current_state == BehaviorState.OPENING_CORRIDOR:
            self._log_task_event(
                "trial_complete",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
                trial_index=previous_trial_index,
                context_id=previous_context_id,
            )
            self._log_task_event(
                "trial_start",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
            )
            return

        if previous_state == BehaviorState.ITI and current_state == BehaviorState.IDLE:
            self._log_task_event(
                "trial_complete",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
                trial_index=previous_trial_index,
                context_id=previous_context_id,
            )
            self._log_task_event(
                "session_complete",
                now_s=now_s,
                session_start_s=session_start_s,
                tick_out=tick_out,
                segment_position_cm=segment_position_cm,
                speed_cm_s=speed_cm_s,
                commands=commands,
                trial_index=previous_trial_index,
                context_id=previous_context_id,
            )
            return

        self._log_task_event(
            "state_transition",
            now_s=now_s,
            session_start_s=session_start_s,
            tick_out=tick_out,
            segment_position_cm=segment_position_cm,
            speed_cm_s=speed_cm_s,
            commands=commands,
            previous_state=previous_state,
        )

    def _log_task_event(
        self,
        event_name: str,
        *,
        now_s: float,
        session_start_s: float,
        tick_out,
        segment_position_cm: float,
        speed_cm_s: float,
        commands: list[Command],
        reason: str | None = None,
        trial_index: int | None = None,
        context_id: int | None = None,
        previous_state: BehaviorState | None = None,
    ) -> None:
        if self._event_logger is None:
            return

        resolved_trial_index = (
            trial_index if trial_index is not None else self.state_machine.current_trial_index
        )
        resolved_context_id = context_id if context_id is not None else tick_out.context_id
        context_payload = self._context_payload(resolved_context_id)
        event = {
            "event": event_name,
            "clock_s": round(now_s - session_start_s, 6),
            "clock_ms": int(round((now_s - session_start_s) * 1000.0)),
            "monotonic_s": round(now_s, 6),
            "trial_index": resolved_trial_index,
            "num_trials": self.config.num_trials,
            "state": tick_out.state.name.lower(),
            "state_code": int(tick_out.state),
            "previous_state": previous_state.name.lower() if previous_state else None,
            "context": context_payload,
            "expected_outcome": self._context_expected_outcome(resolved_context_id),
            "distance": {
                "segment_position_cm": round(float(segment_position_cm), 6),
                "opening_corridor_length_cm": self.config.opening_corridor_length_cm,
                "context_zone_length_cm": self.config.context_zone_length_cm,
                "reward_zone_position_cm": self.config.reward_zone_position_cm,
            },
            "speed_cm_s": round(float(speed_cm_s), 6),
            "scene_id": tick_out.scene_id,
            "flags": int(tick_out.flags),
            "encoder": self._encoder_payload(now_s),
            "commands": [self._command_payload(command) for command in commands],
        }
        if reason is not None:
            event["reason"] = reason
        self._event_logger.log(event)

    def _log_session_stop(
        self,
        *,
        reason: str,
        now_s: float,
        session_start_s: float,
    ) -> None:
        if self._event_logger is None:
            return
        self._event_logger.log(
            {
                "event": "session_stop",
                "clock_s": round(now_s - session_start_s, 6),
                "clock_ms": int(round((now_s - session_start_s) * 1000.0)),
                "monotonic_s": round(now_s, 6),
                "trial_index": self.state_machine.current_trial_index,
                "num_trials": self.config.num_trials,
                "state": self.state_machine.state.name.lower(),
                "state_code": int(self.state_machine.state),
                "context": self._context_payload(self.state_machine.current_context),
                "expected_outcome": self._context_expected_outcome(
                    self.state_machine.current_context
                ),
                "distance": None,
                "speed_cm_s": None,
                "scene_id": None,
                "flags": None,
                "encoder": self._encoder_payload(now_s),
                "commands": [],
                "reason": reason,
                "trials_completed": self.state_machine.trials_completed,
            }
        )

    def _encoder_payload(self, now_s: float) -> dict[str, Any]:
        last_packet_age_s = None
        if self._last_packet_monotonic_s is not None:
            last_packet_age_s = round(now_s - self._last_packet_monotonic_s, 6)

        delta_since_status = None
        if self._last_status_encoder_count is not None:
            delta_since_status = self._encoder_count - self._last_status_encoder_count

        return {
            "raw_count": self._raw_encoder_count,
            "count": self._encoder_count,
            "delta_count_since_last_status": delta_since_status,
            "invert_encoder": self.config.invert_encoder,
            "packets_received": self._packets_received,
            "packets_arriving": self._packets_received > 0,
            "last_packet_age_s": last_packet_age_s,
            "last_packet_timestamp_ms": self._last_packet_timestamp_ms,
            "serial_port": self.config.serial_port,
            "serial_baud": self.config.serial_baud,
        }

    def _context_payload(self, context_id: int) -> dict[str, Any] | None:
        if context_id not in self.config.contexts:
            return None
        context = self.config.context_config(context_id)
        return {
            "id": context.id,
            "scene_id": context.scene_id,
            "audio_cue": context.audio_cue,
            "identity_pulses": context.identity_pulses,
            "reward_ms": context.reward_ms,
            "airpuff_ms": context.airpuff_ms,
            "outcome_events": list(context.resolved_outcome_events()),
        }

    def _context_expected_outcome(self, context_id: int) -> dict[str, Any]:
        if context_id not in self.config.contexts:
            return {"label": "none", "events": []}
        context = self.config.context_config(context_id)
        events = list(context.resolved_outcome_events())
        if self.config.session_type == SessionType.RETRIEVAL:
            return {
                "label": "suppressed_retrieval",
                "events": events,
                "reward_ms": context.reward_ms,
                "airpuff_ms": context.airpuff_ms,
            }
        if not events:
            return {
                "label": "none",
                "events": [],
                "reward_ms": context.reward_ms,
                "airpuff_ms": context.airpuff_ms,
            }
        return {
            "label": "+".join(events),
            "events": events,
            "reward_ms": context.reward_ms,
            "airpuff_ms": context.airpuff_ms,
        }

    def _command_payload(self, command: Command) -> dict[str, Any]:
        return {
            "type": command.type.value,
            "ttl_event": command.ttl_event.value if command.ttl_event else None,
            "context_id": command.context_id,
            "cue_id": command.cue_id,
            "cue_ids": list(command.cue_ids) if command.cue_ids else None,
            "duration_ms": command.duration_ms,
            "pulse_count": command.pulse_count,
        }

    def _build_encoder_reader(self) -> EncoderReader:
        if self.use_mock_hardware:
            counts_per_cm = self.config.encoder_cpr / (
                math.pi * self.config.wheel_diameter_cm
            )
            mock_speed_cm_s = max(5.0, self.config.speed_threshold_cm_s + 12.0)
            counts_per_second = counts_per_cm * mock_speed_cm_s
            if self.config.invert_encoder:
                counts_per_second *= -1.0
            return SyntheticEncoderReader(counts_per_second=counts_per_second)
        return SerialEncoderReader(
            port=self.config.serial_port,
            baudrate=self.config.serial_baud,
        )

    def _shutdown(self, log_paths) -> None:
        if self._log_writer is not None:
            self._log_writer.stop()
        if self._event_logger is not None:
            self._event_logger.close()
        finalize_log_artifacts(log_paths)

        self._executor.shutdown()
        self._udp_sender.close()
        serial_close = getattr(self._encoder_reader, "close", None)
        if callable(serial_close):
            serial_close()
