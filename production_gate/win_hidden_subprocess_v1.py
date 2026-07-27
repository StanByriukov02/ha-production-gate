"""Windows: forbid console-flash child processes (HARD gate).

Desk / prove-null / Dual / git / cmake / Rust CUI bins — any of these
via subprocess will flash a micro console on win32 unless CREATE_NO_WINDOW.

This module:
  1) hidden_run_kwargs() — explicit kwargs for call sites
  2) install_global_no_console_flash() — monkeypatch subprocess.run/Popen
     so a MISSING kwargs path still cannot flash

Opt-out (debug only): HA_ALLOW_CONSOLE_FLASH=1
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

_INSTALLED = False
_ORIG_RUN = subprocess.run
_ORIG_POPEN = subprocess.Popen


def create_no_window_flags() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def startupinfo_hidden() -> Any | None:
    if sys.platform != "win32":
        return None
    si = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    si.wShowWindow = 0  # SW_HIDE
    return si


def hidden_run_kwargs() -> dict[str, Any]:
    """kwargs for subprocess.run / Popen — keep pipes; no DETACHED_PROCESS."""
    kw: dict[str, Any] = {}
    flags = create_no_window_flags()
    if flags:
        kw["creationflags"] = flags
    si = startupinfo_hidden()
    if si is not None:
        kw["startupinfo"] = si
    return kw


def _flash_allowed() -> bool:
    return os.environ.get("HA_ALLOW_CONSOLE_FLASH", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def merge_no_console_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Force CREATE_NO_WINDOW + hidden startupinfo on win32 (unless opt-out)."""
    out = dict(kwargs)
    if sys.platform != "win32" or _flash_allowed():
        return out
    flags = create_no_window_flags()
    if flags:
        # Strip CREATE_NEW_CONSOLE if present — it fights CREATE_NO_WINDOW.
        create_new_console = int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10))
        existing = int(out.get("creationflags") or 0) & ~create_new_console
        out["creationflags"] = existing | flags
    if out.get("startupinfo") is None:
        si = startupinfo_hidden()
        if si is not None:
            out["startupinfo"] = si
    return out


def _run_no_flash(*args: Any, **kwargs: Any) -> Any:
    return _ORIG_RUN(*args, **merge_no_console_kwargs(kwargs))


def _popen_no_flash(*args: Any, **kwargs: Any) -> Any:
    return _ORIG_POPEN(*args, **merge_no_console_kwargs(kwargs))


def install_global_no_console_flash() -> bool:
    """Idempotent. Patches subprocess.run / Popen process-wide on win32.

    Call at production_gate import and at every long-lived entry (serve/shell).
    Returns True if patch is active.
    """
    global _INSTALLED
    if sys.platform != "win32":
        return False
    if _flash_allowed():
        return False
    if _INSTALLED and subprocess.run is _run_no_flash and subprocess.Popen is _popen_no_flash:
        return True
    subprocess.run = _run_no_flash  # type: ignore[assignment]
    subprocess.Popen = _popen_no_flash  # type: ignore[misc, assignment]
    _INSTALLED = True
    return True


def is_global_no_console_flash_installed() -> bool:
    return bool(
        sys.platform == "win32"
        and not _flash_allowed()
        and subprocess.run is _run_no_flash
        and subprocess.Popen is _popen_no_flash
    )


# Install on import — first defense before any gate module can spawn.
install_global_no_console_flash()
