from __future__ import annotations

import ctypes
import ctypes.util
import time
from dataclasses import dataclass

CLOCK_MONOTONIC = 1
TIMER_ABSTIME = 1


class _Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def _load_clock_nanosleep():
    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        return None
    libc = ctypes.CDLL(libc_name, use_errno=True)
    fn = getattr(libc, "clock_nanosleep", None)
    if fn is None:
        return None
    fn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(_Timespec), ctypes.c_void_p]
    fn.restype = ctypes.c_int
    return fn


_CLOCK_NANOSLEEP = _load_clock_nanosleep()


@dataclass
class RealtimeTicker:
    hz: int
    overrun_count: int = 0

    def __post_init__(self) -> None:
        if self.hz <= 0:
            raise ValueError("hz must be > 0")
        self._period_ns = int(1_000_000_000 / self.hz)
        self._next_deadline_ns: int | None = None

    def start(self) -> None:
        self._next_deadline_ns = time.monotonic_ns() + self._period_ns

    def wait_next(self) -> None:
        if self._next_deadline_ns is None:
            self.start()

        assert self._next_deadline_ns is not None
        now_ns = time.monotonic_ns()
        if now_ns > self._next_deadline_ns:
            self.overrun_count += 1
        else:
            self._sleep_until_ns(self._next_deadline_ns)

        self._next_deadline_ns += self._period_ns

    @staticmethod
    def monotonic_s() -> float:
        return time.monotonic()

    @staticmethod
    def monotonic_ms() -> int:
        return int(time.monotonic() * 1000.0)

    @staticmethod
    def _sleep_until_ns(target_ns: int) -> None:
        if _CLOCK_NANOSLEEP is None:
            delay_ns = target_ns - time.monotonic_ns()
            if delay_ns > 0:
                time.sleep(delay_ns / 1_000_000_000)
            return

        ts = _Timespec(tv_sec=target_ns // 1_000_000_000, tv_nsec=target_ns % 1_000_000_000)
        result = _CLOCK_NANOSLEEP(CLOCK_MONOTONIC, TIMER_ABSTIME, ctypes.byref(ts), None)
        if result != 0:
            delay_ns = target_ns - time.monotonic_ns()
            if delay_ns > 0:
                time.sleep(delay_ns / 1_000_000_000)
