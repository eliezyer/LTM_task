from __future__ import annotations

from dataclasses import dataclass

from rpi5_controller.core.commands import Command, CommandType, TTLEvent
from rpi5_controller.core.config import SessionConfig
from rpi5_controller.hardware.audio import WavTriggerController
from rpi5_controller.hardware.gpio import GPIOBackend
from rpi5_controller.hardware.pulse import PulseScheduler


@dataclass
class CommandExecutionResult:
    reward_on: bool = False
    airpuff_on: bool = False


class HardwareCommandExecutor:
    def __init__(
        self,
        config: SessionConfig,
        gpio: GPIOBackend,
        pulse_scheduler: PulseScheduler,
        audio: WavTriggerController,
    ):
        self.config = config
        self.gpio = gpio
        self.pulse_scheduler = pulse_scheduler
        self.audio = audio

        self._ttl_pin_map = {
            TTLEvent.TRIAL_START: config.pinmap.ttl_trial_start,
            TTLEvent.CONTEXT_IDENTITY: config.pinmap.ttl_context_identity,
            TTLEvent.CONTEXT_ENTRY: config.pinmap.ttl_context_entry,
            TTLEvent.REWARD: config.pinmap.ttl_reward,
            TTLEvent.AIRPUFF: config.pinmap.ttl_airpuff,
            TTLEvent.LICK_ONSET: config.pinmap.ttl_lick,
            TTLEvent.ITI_START: config.pinmap.ttl_iti_start,
        }

    def setup(self) -> None:
        output_pins = {
            self.config.pinmap.water_solenoid,
            self.config.pinmap.air_solenoid,
            *self._ttl_pin_map.values(),
        }
        for pin in output_pins:
            self.gpio.setup_output(pin)
            self.gpio.write(pin, 0)
        self.audio.setup()

    def execute(self, commands: list[Command], now_s: float) -> CommandExecutionResult:
        result = CommandExecutionResult()
        for command in commands:
            if command.type == CommandType.AUDIO_START_CONTEXT:
                if command.context_id is None:
                    raise ValueError("AUDIO_START_CONTEXT requires context_id")
                self.audio.start_context(command.context_id)

            elif command.type == CommandType.AUDIO_STOP_ALL:
                self.audio.stop_all()

            elif command.type == CommandType.SOLENOID_REWARD:
                if command.duration_ms is None:
                    raise ValueError("SOLENOID_REWARD requires duration_ms")
                self.pulse_scheduler.schedule_pulse(
                    pin=self.config.pinmap.water_solenoid,
                    duration_ms=command.duration_ms,
                    now_s=now_s,
                )
                result.reward_on = True

            elif command.type == CommandType.SOLENOID_AIRPUFF:
                if command.duration_ms is None:
                    raise ValueError("SOLENOID_AIRPUFF requires duration_ms")
                self.pulse_scheduler.schedule_pulse(
                    pin=self.config.pinmap.air_solenoid,
                    duration_ms=command.duration_ms,
                    now_s=now_s,
                )
                result.airpuff_on = True

            elif command.type == CommandType.TTL_PULSE:
                if command.ttl_event is None:
                    raise ValueError("TTL_PULSE requires ttl_event")
                ttl_pin = self._ttl_pin_map[command.ttl_event]
                self.pulse_scheduler.schedule_pulse(
                    pin=ttl_pin,
                    duration_ms=self.config.ttl_pulse_width_ms,
                    now_s=now_s,
                )

            elif command.type == CommandType.TTL_PULSE_TRAIN:
                if command.ttl_event is None or command.pulse_count is None:
                    raise ValueError("TTL_PULSE_TRAIN requires ttl_event and pulse_count")
                ttl_pin = self._ttl_pin_map[command.ttl_event]
                self.pulse_scheduler.schedule_pulse_train(
                    pin=ttl_pin,
                    pulses=command.pulse_count,
                    pulse_width_ms=self.config.ttl_pulse_width_ms,
                    gap_ms=self.config.ttl_train_gap_ms,
                    now_s=now_s,
                )

        return result

    def update(self, now_s: float) -> None:
        self.pulse_scheduler.update(now_s)

    def shutdown(self) -> None:
        self.audio.stop_all()
        self.gpio.cleanup()
