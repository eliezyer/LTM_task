from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rpi5_controller.core.commands import Command, CommandType
from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.enums import UdpFlags
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

        self._gpio = MockGPIOBackend() if use_mock_hardware else RPiGPIOBackend()
        self._encoder_reader = self._build_encoder_reader()
        self._udp_sender = MockUdpSender() if use_mock_hardware else UdpSender(
            config.udp_target_ip,
            config.udp_target_port,
        )

        self._audio = WavTriggerController(
            gpio=self._gpio,
            context_pin_map={
                1: config.pinmap.wav_context_1,
                2: config.pinmap.wav_context_2,
                3: config.pinmap.wav_context_3,
            },
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

        start_now_s = self.ticker.monotonic_s()
        started = self.state_machine.start_session(start_now_s)
        self._process_commands(started.commands, start_now_s)

        # Broadcast initial scene state immediately before entering periodic loop.
        self._send_udp(
            position_cm=self.position_decoder.segment_position_cm(self._encoder_count),
            scene_id=started.scene_id,
            flags=started.flags,
        )

        start_monotonic_s = self.ticker.monotonic_s()
        self.ticker.start()

        try:
            while True:
                now_s = self.ticker.monotonic_s()
                elapsed_s = now_s - start_monotonic_s
                if self.max_seconds is not None and elapsed_s >= self.max_seconds:
                    break

                packet = self._encoder_reader.read_latest_packet()
                if packet is not None:
                    self._encoder_count = packet.encoder_count

                segment_position_cm = self.position_decoder.segment_position_cm(
                    self._encoder_count
                )
                speed_cm_s = self.speed_estimator.update(self._encoder_count, now_s)
                lick_level, lick_onset, _ = self._lick.sample()

                tick_out = self.state_machine.tick(
                    TickInput(
                        now_s=now_s,
                        segment_position_cm=segment_position_cm,
                        speed_cm_s=speed_cm_s,
                        lick_onset=lick_onset,
                    )
                )
                exec_result = self._process_commands(tick_out.commands, now_s)

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
                if self.state_machine.session_complete:
                    break

                self.ticker.wait_next()
        finally:
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

    def _build_encoder_reader(self) -> EncoderReader:
        if self.use_mock_hardware:
            counts_per_cm = self.config.encoder_cpr / (
                math.pi * self.config.wheel_diameter_cm
            )
            mock_speed_cm_s = max(5.0, self.config.speed_threshold_cm_s + 12.0)
            return SyntheticEncoderReader(counts_per_second=counts_per_cm * mock_speed_cm_s)
        return SerialEncoderReader(
            port=self.config.serial_port,
            baudrate=self.config.serial_baud,
        )

    def _shutdown(self, log_paths) -> None:
        if self._log_writer is not None:
            self._log_writer.stop()
        finalize_log_artifacts(log_paths)

        self._executor.shutdown()
        self._udp_sender.close()
        serial_close = getattr(self._encoder_reader, "close", None)
        if callable(serial_close):
            serial_close()
