from __future__ import annotations

from dataclasses import dataclass

from rpi5_controller.core.commands import Command, CommandType, TTLEvent
from rpi5_controller.core.config import SessionConfig
from rpi5_controller.core.enums import BehaviorState, SessionType, UdpFlags
from rpi5_controller.core.iti import ITISampler
from rpi5_controller.core.randomization import ContextBlockRandomizer
from rpi5_controller.core.task_flow import build_event_commands


@dataclass(frozen=True)
class TickInput:
    now_s: float
    segment_position_cm: float
    speed_cm_s: float
    lick_onset: bool


@dataclass
class TickOutput:
    state: BehaviorState
    scene_id: int
    context_id: int
    flags: UdpFlags
    commands: list[Command]
    reward_on: bool
    airpuff_on: bool


class BehaviorStateMachine:
    def __init__(self, config: SessionConfig):
        self.config = config
        self.state = BehaviorState.IDLE
        self.session_complete = False
        self.trials_completed = 0
        self.current_context = 0
        self._iti_end_s: float | None = None
        self._outcome_end_s: float | None = None
        self._stall_start_s: float | None = None

        self._randomizer = ContextBlockRandomizer(
            num_trials=config.num_trials,
            contexts=config.context_ids,
            seed=config.seed,
            fixed_sequence=tuple(config.context_sequence)
            if config.context_sequence is not None
            else None,
        )
        self._iti_sampler = ITISampler(config.iti_distribution, seed=config.seed)

    @property
    def planned_context_sequence(self) -> list[int]:
        return self._randomizer.sequence

    @property
    def current_trial_index(self) -> int:
        return min(self.trials_completed + 1, self.config.num_trials)

    def start_session(self, now_s: float) -> TickOutput:
        if self.state != BehaviorState.IDLE:
            raise RuntimeError("Session already started")

        commands: list[Command] = []
        self.current_context = self._randomizer.next_context()
        self._enter_opening_corridor(commands)
        return self._build_output(commands=commands, freeze=False, reward_on=False, airpuff_on=False)

    def tick(self, tick_input: TickInput) -> TickOutput:
        commands: list[Command] = []
        reward_on = False
        airpuff_on = False
        freeze = False

        if tick_input.lick_onset and self.state != BehaviorState.IDLE:
            commands.append(
                Command(type=CommandType.TTL_PULSE, ttl_event=TTLEvent.LICK_ONSET)
            )

        if self.state == BehaviorState.OPENING_CORRIDOR:
            freeze = tick_input.speed_cm_s <= 0.0
            if tick_input.segment_position_cm >= self.config.opening_corridor_length_cm:
                self._enter_context_zone(commands)

        elif self.state == BehaviorState.CONTEXT_ZONE:
            freeze = tick_input.speed_cm_s <= 0.0
            if freeze:
                if self._stall_start_s is None:
                    self._stall_start_s = tick_input.now_s
                elif tick_input.now_s - self._stall_start_s >= self.config.stall_timeout_s:
                    self._enter_iti(commands, tick_input.now_s)
            else:
                self._stall_start_s = None

            if (
                self.state == BehaviorState.CONTEXT_ZONE
                and tick_input.segment_position_cm >= self.config.reward_zone_position_cm
            ):
                if self.config.session_type == SessionType.RETRIEVAL:
                    self._enter_iti(commands, tick_input.now_s)
                else:
                    outcome_events = self._current_context_config().resolved_outcome_events()
                    if outcome_events:
                        self._enter_outcome_zone(commands, tick_input.now_s, outcome_events)
                    else:
                        self._enter_iti(commands, tick_input.now_s)

        elif self.state == BehaviorState.OUTCOME_ZONE:
            if (
                self._outcome_end_s is not None
                and tick_input.now_s >= self._outcome_end_s
            ):
                self._enter_iti(commands, tick_input.now_s)

        elif self.state == BehaviorState.ITI:
            if self._iti_end_s is not None and tick_input.now_s >= self._iti_end_s:
                self.trials_completed += 1
                if self.trials_completed >= self.config.num_trials:
                    self.state = BehaviorState.IDLE
                    self.session_complete = True
                    self.current_context = 0
                else:
                    self.current_context = self._randomizer.next_context()
                    self._enter_opening_corridor(commands)

        reward_on = reward_on or any(
            cmd.type == CommandType.SOLENOID_REWARD for cmd in commands
        )
        airpuff_on = airpuff_on or any(
            cmd.type == CommandType.SOLENOID_AIRPUFF for cmd in commands
        )

        return self._build_output(
            commands=commands,
            freeze=freeze,
            reward_on=reward_on,
            airpuff_on=airpuff_on,
        )

    def _enter_opening_corridor(self, commands: list[Command]) -> None:
        self.state = BehaviorState.OPENING_CORRIDOR
        self._outcome_end_s = None
        self._stall_start_s = None
        commands.extend(
            build_event_commands(
                self.config,
                "trial_start",
                context=self._current_context_config(),
            )
        )

    def _enter_context_zone(self, commands: list[Command]) -> None:
        self.state = BehaviorState.CONTEXT_ZONE
        self._outcome_end_s = None
        self._stall_start_s = None
        commands.extend(
            build_event_commands(
                self.config,
                "context_entry",
                context=self._current_context_config(),
            )
        )

    def _enter_outcome_zone(
        self,
        commands: list[Command],
        now_s: float,
        outcome_events: tuple[str, ...],
    ) -> None:
        self.state = BehaviorState.OUTCOME_ZONE
        self._stall_start_s = None
        self._outcome_end_s = now_s + self.config.outcome_zone_duration_s
        context = self._current_context_config()

        commands.extend(
            build_event_commands(
                self.config,
                "outcome_start",
                context=context,
            )
        )

        outcome_ttl_duration_ms = max(
            1,
            int(round(self.config.outcome_zone_duration_s * 1000.0)),
        )
        commands.append(
            Command(
                type=CommandType.TTL_PULSE,
                ttl_event=TTLEvent.OUTCOME_START,
                duration_ms=outcome_ttl_duration_ms,
            )
        )

        for event_name in outcome_events:
            commands.extend(
                build_event_commands(
                    self.config,
                    event_name,
                    context=context,
                )
            )

    def _enter_iti(self, commands: list[Command], now_s: float) -> None:
        self.state = BehaviorState.ITI
        self._outcome_end_s = None
        self._stall_start_s = None
        iti_duration = self._iti_sampler.sample_seconds()
        self._iti_end_s = now_s + iti_duration
        commands.extend(
            build_event_commands(
                self.config,
                "iti_start",
                context=self._current_context_config(),
            )
        )

    def _current_context_config(self):
        return self.config.context_config(self.current_context)

    def _build_output(
        self,
        commands: list[Command],
        freeze: bool,
        reward_on: bool,
        airpuff_on: bool,
    ) -> TickOutput:
        scene_id = 0
        if self.state == BehaviorState.CONTEXT_ZONE:
            scene_id = self._current_context_config().scene_id
        elif self.state == BehaviorState.OUTCOME_ZONE:
            scene_id = self.config.outcome_scene_id

        flags = UdpFlags.NONE
        if any(cmd.type == CommandType.TELEPORT for cmd in commands):
            flags |= UdpFlags.TELEPORT
        if self.state == BehaviorState.ITI:
            flags |= UdpFlags.ITI_ACTIVE
        if self.state == BehaviorState.OUTCOME_ZONE:
            flags |= UdpFlags.OUTCOME_ACTIVE
        if freeze and self.state in {
            BehaviorState.OPENING_CORRIDOR,
            BehaviorState.CONTEXT_ZONE,
        }:
            flags |= UdpFlags.FREEZE

        return TickOutput(
            state=self.state,
            scene_id=scene_id,
            context_id=self.current_context,
            flags=flags,
            commands=commands,
            reward_on=reward_on,
            airpuff_on=airpuff_on,
        )
