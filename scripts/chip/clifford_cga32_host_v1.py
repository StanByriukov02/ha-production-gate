"""CGA32 host geo_prod — persistent cxx gp_cli session or python oracle fallback."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Literal

_REPO = Path(__file__).resolve().parents[2]

HostBackend = Literal["cxx", "oracle"]


class CxxGpCliSession:
    """One long-lived gp_cli — amortizes subprocess spawn for traverse hot loops."""

    def __init__(self, exe: Path) -> None:
        self._exe = exe
        self._proc = subprocess.Popen(
            [str(exe)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def cga32_geo_prod(self, rs1_hex: str, rs2_hex: str) -> str:
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("gp_cli session not open")
        self._proc.stdin.write(f"cga32_geo_prod {rs1_hex.lower()} {rs2_hex.lower()}\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            err = (self._proc.stderr.read() if self._proc.stderr else "")[-300:]
            raise RuntimeError(f"gp_cli eof: {err}")
        doc = json.loads(line.strip())
        if doc.get("error"):
            raise RuntimeError(doc["error"])
        rd = doc.get("rd_hex")
        if not rd:
            raise RuntimeError("missing rd_hex")
        return str(rd).lower()

    def close(self) -> None:
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except OSError:
            pass
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def __enter__(self) -> CxxGpCliSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


_session: CxxGpCliSession | None = None


def _discover_gp_cli() -> Path | None:
    try:
        from dogfood_platform._clifford_soft_gp_build_v1 import cmake_build_clifford_soft_gp, find_exe

        build = cmake_build_clifford_soft_gp()
        return find_exe(build, "clifford_gp_cli")
    except (subprocess.CalledProcessError, RuntimeError):
        return None


def resolve_cga32_host_backend(prefer: HostBackend = "cxx") -> HostBackend:
    if prefer == "oracle":
        return "oracle"
    return "cxx" if _discover_gp_cli() is not None else "oracle"


def cga32_geo_prod_host(
    rs1_hex: str,
    rs2_hex: str,
    *,
    backend: HostBackend | None = None,
    session: CxxGpCliSession | None = None,
) -> str:
    """delta ∘ acc on motor512 — host path (cxx preferred)."""
    bk = backend or resolve_cga32_host_backend()
    if bk == "cxx":
        global _session
        active = session or _session
        if active is None:
            exe = _discover_gp_cli()
            if exe is None:
                bk = "oracle"
            else:
                active = CxxGpCliSession(exe)
                if session is None:
                    _session = active
        if bk == "cxx" and active is not None:
            return active.cga32_geo_prod(rs1_hex, rs2_hex)

    from scripts.chip.clifford_cga32_oracle_v1 import Cga32Motor

    a = Cga32Motor.from_bf16_coeffs(_motor512_lanes(rs1_hex))
    b = Cga32Motor.from_bf16_coeffs(_motor512_lanes(rs2_hex))
    return a.geo_prod(b).to_motor512_hex()


def _motor512_lanes(h: str) -> list[int]:
    w = int(h.lower().replace("0x", ""), 16)
    return [(w >> (16 * i)) & 0xFFFF for i in range(32)]


def close_cga32_host_session() -> None:
    global _session
    if _session is not None:
        _session.close()
        _session = None


def host_session_status() -> dict[str, Any]:
    exe = _discover_gp_cli()
    return {
        "gp_cli": str(exe) if exe else None,
        "backend_default": resolve_cga32_host_backend(),
        "session_open": _session is not None,
    }
