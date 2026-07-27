"""Atomic JSON read/write with per-path locks — desk concurrency without corrupt files.

TABU: pretend multi-user accounts · product_ready.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _lock_for(path: Path) -> threading.RLock:
    key = _key(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[key] = lock
        return lock


def atomic_write_text(path: Path, payload: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    lock = _lock_for(path)
    with lock:
        tmp.write_text(payload, encoding="utf-8")
        last_err: Exception | None = None
        for attempt in range(12):
            try:
                os.replace(tmp, path)
                return
            except OSError as exc:
                last_err = exc
                # Windows: destination briefly locked by concurrent reader
                time.sleep(0.01 * (attempt + 1))
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass
        raise OSError(f"atomic replace failed for {path}: {last_err}") from last_err


def atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    payload = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(path, payload)


def atomic_read_text(path: Path) -> str:
    path = Path(path)
    lock = _lock_for(path)
    with lock:
        return path.read_text(encoding="utf-8")


def atomic_read_json(path: Path) -> dict[str, Any]:
    raw = atomic_read_text(path)
    if not raw.strip():
        raise json.JSONDecodeError("empty", raw, 0)
    return json.loads(raw)
