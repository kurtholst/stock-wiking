"""Background runs for the Stars scan and the deep alpha analysis.

One run at a time across processes: the app's "Run now" buttons and the
scheduled systemd job share a file lock in data/, so they never overlap
(and never double the EPO request rate).
"""

from __future__ import annotations

import datetime
import fcntl
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LOCK_FILE = _DATA_DIR / "scan.lock"

Progress = Callable[[int, int, str], None]


class RunBusyError(RuntimeError):
    pass


@contextmanager
def scan_lock(blocking: bool = False) -> Iterator[None]:
    """Exclusive cross-process lock for EPO-heavy runs."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LOCK_FILE, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as e:
            raise RunBusyError("Another scan is already running") from e
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _lock_held_elsewhere() -> bool:
    try:
        with scan_lock():
            return False
    except RunBusyError:
        return True


_state_lock = threading.Lock()
_state: dict = {
    "kind": None,
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "step": 0,
    "total": 0,
    "message": "",
    "error": None,
}
_started_monotonic = 0.0


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def get_status() -> dict:
    with _state_lock:
        status = dict(_state)
    status["elapsed_s"] = round(time.monotonic() - _started_monotonic) if status["status"] == "running" else None
    # A scheduled run (separate process) holds the lock without touching our state
    status["external_running"] = status["status"] != "running" and _lock_held_elsewhere()
    return status


def start_run(kind: str, fn: Callable[[Progress], object]) -> dict:
    """Start fn(progress) in a background thread. Raises RunBusyError if busy."""
    global _started_monotonic
    with _state_lock:
        if _state["status"] == "running":
            raise RunBusyError(f"A {_state['kind']} run is already in progress")
    if _lock_held_elsewhere():
        raise RunBusyError("A scheduled run is in progress")

    def progress(step: int, total: int, message: str) -> None:
        with _state_lock:
            _state.update(step=step, total=total, message=message)

    def worker() -> None:
        try:
            with scan_lock():
                fn(progress)
            with _state_lock:
                _state.update(status="done", finished_at=_now(), message="Finished", step=_state["total"])
        except Exception as e:
            logger.exception("%s run failed", kind)
            with _state_lock:
                _state.update(status="error", finished_at=_now(), error=str(e))

    with _state_lock:
        _state.update(
            kind=kind, status="running", started_at=_now(), finished_at=None,
            step=0, total=0, message="Starting", error=None,
        )
        _started_monotonic = time.monotonic()
    threading.Thread(target=worker, name=f"{kind}-run", daemon=True).start()
    return get_status()
