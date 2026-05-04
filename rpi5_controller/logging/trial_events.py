from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


class TrialEventLogger:
    def __init__(
        self,
        path: Path,
        *,
        stream: TextIO | None = None,
        echo_to_terminal: bool = True,
    ) -> None:
        self.path = path
        self.stream = stream if stream is not None else sys.stdout
        self.echo_to_terminal = echo_to_terminal
        self._handle: TextIO | None = None

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8", buffering=1)

    def log(self, event: dict[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("TrialEventLogger.start() must be called before log()")

        event = dict(event)
        event.setdefault("wall_time", datetime.now().isoformat(timespec="milliseconds"))
        line = json.dumps(event, sort_keys=True, default=_json_default)
        self._handle.write(line + "\n")

        if self.echo_to_terminal:
            print(_format_terminal_event(event), file=self.stream, flush=True)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _format_terminal_event(event: dict[str, Any]) -> str:
    clock_s = float(event.get("clock_s", 0.0))
    event_name = str(event.get("event", "event"))
    state = str(event.get("state", "unknown"))
    trial_index = event.get("trial_index")
    num_trials = event.get("num_trials")

    trial_label = "-"
    if trial_index is not None and num_trials is not None:
        trial_label = f"{trial_index}/{num_trials}"

    context = event.get("context")
    context_id = "-"
    scene_id = "-"
    if isinstance(context, dict):
        context_id = context.get("id", "-")
        scene_id = context.get("scene_id", "-")

    outcome = event.get("expected_outcome")
    outcome_label = "-"
    if isinstance(outcome, dict):
        outcome_label = str(outcome.get("label", "-"))

    distance = event.get("distance")
    pos_label = "-"
    if isinstance(distance, dict) and distance.get("segment_position_cm") is not None:
        pos_label = f"{float(distance['segment_position_cm']):.2f}cm"

    encoder_label = "enc=-"
    encoder = event.get("encoder")
    if isinstance(encoder, dict):
        count = encoder.get("count")
        raw_count = encoder.get("raw_count")
        delta_count = encoder.get("delta_count_since_last_status")
        packets = encoder.get("packets_received")
        age = encoder.get("last_packet_age_s")
        age_label = "-" if age is None else f"{float(age):.3f}s"
        encoder_label = (
            f"enc={count} raw={raw_count} d={delta_count} "
            f"pkts={packets} age={age_label}"
        )

    reason = event.get("reason")
    reason_label = f" reason={reason}" if reason else ""
    return (
        f"[task] t={clock_s:8.3f}s {event_name:<16} "
        f"trial={trial_label} state={state} ctx={context_id} "
        f"scene={scene_id} outcome={outcome_label} pos={pos_label} "
        f"{encoder_label}{reason_label}"
    )
