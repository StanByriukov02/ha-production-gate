"""ManipulatorKinematicsPort v1 — Rust crown FK/IK/dynamics; Python glue only.

TABU: claim RT servo · claim flight arm · Python FK truth.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Protocol

_REPO = Path(__file__).resolve().parents[1]
_CONTRACT = _REPO / "fixtures" / "robot" / "manipulator_kinematics_port_v0.json"
_CHAIN = _REPO / "fixtures" / "robot" / "lunar_manipulator_chain_v1.json"

PROOF_TIER = "MANIPULATOR_KINEMATICS_SLICE"
BACKEND_RUST_SERIAL = "manipulator_rust_serial_arm_v1"
BACKEND_EUCLIDEAN_BAD = "manipulator_euclidean_bad_inject_v1"


def load_contract() -> dict[str, Any]:
    return json.loads(_CONTRACT.read_text(encoding="utf-8"))


def load_chain() -> dict[str, Any]:
    return json.loads(_CHAIN.read_text(encoding="utf-8"))


class ManipulatorKinematicsPort(Protocol):
    def fk(self, q: list[float]) -> dict[str, Any]: ...
    def ik(self, target_x: float, target_y: float, *, q0: list[float] | None = None) -> dict[str, Any]: ...


def _native_call(payload: dict[str, Any], *, build: bool = True) -> dict[str, Any]:
    from dogfood_platform.manipulator_kinematics_backend_native_v1 import run_manipulator_kinematics_native

    return run_manipulator_kinematics_native(payload, build=build)


def chain_native_params(chain_spec: dict[str, Any]) -> dict[str, Any]:
    """Rust crown params from resolved chain IR spec."""
    ll = chain_spec.get("link_lengths_m")
    if not ll:
        return {}
    masses = chain_spec.get("link_masses_kg") or [0.1] * len(ll)
    return {"link_lengths": list(ll), "link_masses": list(masses)}


class RustSerialArmBackend:
    """Crown backend — all joint-space truth from Rust bin."""

    source_id = BACKEND_RUST_SERIAL
    chain_spec: dict[str, Any] | None = None

    def _payload(self, op: str, **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"op": op, **extra}
        if self.chain_spec:
            payload.update(chain_native_params(self.chain_spec))
        return payload

    def fk(self, q: list[float], *, g: float = 1.62, build: bool = True) -> dict[str, Any]:
        out = _native_call(self._payload("fk", q=q, g=g), build=build)
        return {"source_id": self.source_id, "verdict": out["verdict"], **out["report"]}

    def ik(
        self,
        target_x: float,
        target_y: float,
        *,
        q0: list[float] | None = None,
        g: float = 1.62,
        build: bool = True,
    ) -> dict[str, Any]:
        payload = self._payload("ik", target_x=target_x, target_y=target_y, g=g)
        if q0:
            payload["q"] = q0
        out = _native_call(payload, build=build)
        return {"source_id": self.source_id, "verdict": out["verdict"], **out["report"]}

    def jacobian(self, q: list[float], *, g: float = 1.62, build: bool = True) -> dict[str, Any]:
        out = _native_call(self._payload("jacobian", q=q, g=g), build=build)
        return {"source_id": self.source_id, "verdict": out["verdict"], **out["report"]}

    def symplectic_step(
        self,
        *,
        q: list[float],
        q_dot: list[float],
        torques: list[float] | None = None,
        steps: int = 100,
        dt: float = 0.005,
        g: float = 1.62,
        build: bool = True,
    ) -> dict[str, Any]:
        n = len(q)
        payload = self._payload(
            "symplectic_step",
            q=q,
            q_dot=q_dot,
            torques=torques or [0.0] * n,
            steps=steps,
            dt=dt,
            g=g,
        )
        out = _native_call(payload, build=build)
        return {"source_id": self.source_id, "verdict": out["verdict"], **out["report"]}

    def fk_ik_roundtrip(self, q: list[float], *, g: float = 1.62, build: bool = True) -> dict[str, Any]:
        out = _native_call(self._payload("fk_ik_roundtrip", q=q, g=g), build=build)
        return {"source_id": self.source_id, "verdict": out["verdict"], **out["report"]}


class EuclideanBadInjectBackend:
    """Falsifier — adds joint error without manifold respect."""

    source_id = BACKEND_EUCLIDEAN_BAD

    def fk(self, q: list[float], **_kwargs: Any) -> dict[str, Any]:
        # Wrong: treat angles as x,y offsets (classic bad inject)
        x = sum(q)
        y = sum(qi * qi for qi in q)
        return {
            "source_id": self.source_id,
            "ee_x": x,
            "ee_y": y,
            "ee_theta": q[-1] if q else 0.0,
            "bad_inject": True,
        }


def jacobian_finite_diff(
    backend: RustSerialArmBackend,
    q: list[float],
    *,
    eps: float = 1e-5,
    build: bool = True,
) -> tuple[float, float]:
    """Returns max relative error vs analytic J."""
    analytic = backend.jacobian(q, build=build)
    n = len(q)
    j_an = analytic["j_flat"]
    j_fd = [0.0] * (2 * n)
    f0 = backend.fk(q, build=build)
    for j in range(n):
        qp = list(q)
        qm = list(q)
        qp[j] += eps
        qm[j] -= eps
        fp = backend.fk(qp, build=build)
        fm = backend.fk(qm, build=build)
        j_fd[j] = (fp["ee_x"] - fm["ee_x"]) / (2.0 * eps)
        j_fd[n + j] = (fp["ee_y"] - fm["ee_y"]) / (2.0 * eps)
    max_rel = 0.0
    for k in range(2 * n):
        denom = max(abs(j_an[k]), 1e-9)
        max_rel = max(max_rel, abs(j_an[k] - j_fd[k]) / denom)
    return max_rel, analytic["j_flat"][0]


def compare_backends_diverge(q: list[float]) -> dict[str, Any]:
    good = RustSerialArmBackend().fk(q, build=False)
    bad = EuclideanBadInjectBackend().fk(q)
    dx = abs(good["ee_x"] - bad["ee_x"])
    dy = abs(good["ee_y"] - bad["ee_y"])
    return {
        "good": good,
        "bad": bad,
        "pos_error_m": math.sqrt(dx * dx + dy * dy),
        "diverge": math.sqrt(dx * dx + dy * dy) >= 0.02,
    }


def run_manipulator_kinematics_smoke(*, build: bool = True) -> dict[str, Any]:
    backend = RustSerialArmBackend()
    q = [0.35, 0.42, -0.18]
    contract = load_contract()
    fals = contract.get("falsifiers") or {}

    fk = backend.fk(q, build=build)
    ik = backend.ik(fk["ee_x"], fk["ee_y"], q0=q, build=build)
    roundtrip = backend.fk_ik_roundtrip(q, build=build)
    j_err, _ = jacobian_finite_diff(backend, q, build=build)
    sym = backend.symplectic_step(q=q, q_dot=[0.05, 0.0, -0.02], steps=200, dt=0.005, build=build)
    div = compare_backends_diverge(q)

    rt_err = roundtrip.get("roundtrip_error_m")
    if rt_err is None:
        rt_err = 99.0

    checks = {
        "F_fk_finite": math.isfinite(fk["ee_x"]) and math.isfinite(fk["ee_y"]),
        "F_ik_converged": ik.get("converged") is True,
        "F_fk_ik_roundtrip": float(rt_err) <= float(fals.get("fk_ik_roundtrip_max_m") or 0.005),
        "F_jacobian_fd": j_err <= float(fals.get("jacobian_fd_rel_max") or 0.01),
        "F_symplectic_drift": float(sym.get("max_rel_drift") or 99)
        <= float(fals.get("symplectic_energy_drift_max") or 0.45),
        "F_bad_inject_diverge": div["diverge"],
        "F_native_verdict_roundtrip": roundtrip.get("verdict", "").endswith("PASS")
        if "verdict" in roundtrip
        else str(backend.fk_ik_roundtrip(q, build=build).get("verdict", "")).endswith("PASS"),
    }
    fail = [k for k, v in checks.items() if not v]
    return {
        "verdict": "MANIPULATOR_KINEMATICS_PORT_PASS" if not fail else "MANIPULATOR_KINEMATICS_PORT_FAIL",
        "proof_tier": PROOF_TIER,
        "backend": BACKEND_RUST_SERIAL,
        "checks": checks,
        "fail": fail,
        "fk_sample": fk,
        "ik_sample": ik,
        "roundtrip_error_m": roundtrip.get("roundtrip_error_m"),
        "jacobian_fd_rel_err": round(j_err, 6),
        "symplectic_drift": sym.get("max_rel_drift"),
        "bad_inject_pos_error_m": round(div["pos_error_m"], 4),
        "contract": str(_CONTRACT.relative_to(_REPO)).replace("\\", "/"),
    }


if __name__ == "__main__":
    print(json.dumps(run_manipulator_kinematics_smoke(), indent=2))
