from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from rpi5_controller.logging.log_entry import LogEntry
from rpi5_controller.logging.ring_buffer import ThreadSafeRingBuffer


@dataclass
class LogPaths:
    tmp_binary_path: Path
    tmp_metadata_path: Path
    tmp_event_path: Path
    final_binary_path: Path
    final_metadata_path: Path
    final_event_path: Path


class AsyncLogWriter:
    def __init__(
        self,
        ring_buffer: ThreadSafeRingBuffer[LogEntry],
        binary_path: Path,
    ):
        self._ring_buffer = ring_buffer
        self._binary_path = binary_path
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="log-writer", daemon=True)

    def start(self) -> None:
        self._binary_path.parent.mkdir(parents=True, exist_ok=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._ring_buffer.close()
        self._thread.join(timeout=10.0)

    def _run(self) -> None:
        with self._binary_path.open("wb") as handle:
            while True:
                entry = self._ring_buffer.pop(timeout_s=0.2)
                if entry is not None:
                    handle.write(entry.pack())
                elif self._stop_event.is_set() and self._ring_buffer.closed:
                    break

    @staticmethod
    def write_metadata(path: Path, metadata: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def build_log_paths(
    tmp_dir: str,
    final_dir: str,
    session_tag: str,
) -> LogPaths:
    tmp_base = Path(tmp_dir)
    final_base = Path(final_dir)
    return LogPaths(
        tmp_binary_path=tmp_base / f"{session_tag}.bin",
        tmp_metadata_path=tmp_base / f"{session_tag}.json",
        tmp_event_path=tmp_base / f"{session_tag}.events.jsonl",
        final_binary_path=final_base / f"{session_tag}.bin",
        final_metadata_path=final_base / f"{session_tag}.json",
        final_event_path=final_base / f"{session_tag}.events.jsonl",
    )


def finalize_log_artifacts(paths: LogPaths) -> None:
    paths.final_binary_path.parent.mkdir(parents=True, exist_ok=True)
    paths.final_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(paths.tmp_binary_path, paths.final_binary_path)
    shutil.copy2(paths.tmp_metadata_path, paths.final_metadata_path)
    shutil.copy2(paths.tmp_event_path, paths.final_event_path)
