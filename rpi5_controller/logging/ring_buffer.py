from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class ThreadSafeRingBuffer(Generic[T]):
    maxlen: int
    _buffer: deque[T] = field(default_factory=deque)
    _condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.Lock())
    )
    _closed: bool = False
    dropped_items: int = 0

    def push(self, item: T) -> None:
        with self._condition:
            if len(self._buffer) >= self.maxlen:
                self._buffer.popleft()
                self.dropped_items += 1
            self._buffer.append(item)
            self._condition.notify()

    def pop(self, timeout_s: float | None = None) -> T | None:
        with self._condition:
            if not self._buffer and not self._closed:
                self._condition.wait(timeout=timeout_s)

            if self._buffer:
                return self._buffer.popleft()
            return None

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    def __len__(self) -> int:
        with self._condition:
            return len(self._buffer)
