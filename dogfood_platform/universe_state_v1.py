"""Universe kernel · state bus v0 — schema + validation."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_LAW_REGISTRY = _REPO / "results" / "platform_bpass" / "universe" / "law_registry_v1.json"
_BUS_SCHEMA = _REPO / "results" / "platform_bpass" / "universe" / "universe_state_bus_schema_v1.json"
_VAULT_CANON = "public_teaching_bind"

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass
class EpsilonRow:
    hop_id: str
    epsilon_name: str
    measured: dict[str, Any]
    unit: str = ""
    within_budget: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HopState:
    hop_id: str
    law_id: str
    backend: str
    verdict: str
    state_delta: dict[str, Any] = field(default_factory=dict)
    source_receipt: str = ""
    epsilon_row: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UniverseStateBus:
    bus_id: str
    world_id: str
    corridor_id: str
    inputs_hash: str
    hops: list[HopState]
    epsilon: list[EpsilonRow]
    metric: dict[str, Any]
    verdict: str
    backend_manifest: list[str]
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    falsifier: str = (
        "metric changes without inputs_hash/law change · hop without epsilon row · "
        "if-then threshold without physics backend"
    )
    vault_canon: str = _VAULT_CANON

    def to_dict(self) -> dict[str, Any]:
        return {
            "bus_id": self.bus_id,
            "world_id": self.world_id,
            "corridor_id": self.corridor_id,
            "inputs_hash": self.inputs_hash,
            "hops": [h.to_dict() for h in self.hops],
            "epsilon": [e.to_dict() for e in self.epsilon],
            "metric": self.metric,
            "verdict": self.verdict,
            "backend_manifest": self.backend_manifest,
            "falsifier": self.falsifier,
            "vault_canon": self.vault_canon,
            "timestamp_utc": self.timestamp_utc,
        }


def load_law_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or _LAW_REGISTRY
    if not p.is_file():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def law_by_id(registry: dict[str, Any], law_id: str) -> dict[str, Any]:
    for row in registry.get("laws") or []:
        if row.get("law_id") == law_id:
            return row
    raise KeyError(f"unknown law_id: {law_id}")


def validate_state_bus(bus: UniverseStateBus | dict[str, Any]) -> None:
    data = bus.to_dict() if isinstance(bus, UniverseStateBus) else bus
    if not _HASH_RE.match(str(data.get("inputs_hash") or "")):
        raise ValueError("inputs_hash must be sha256:…")
    hops = data.get("hops") or []
    eps = data.get("epsilon") or []
    if not hops:
        raise ValueError("hops empty")
    if not eps:
        raise ValueError("epsilon empty — multi-hop requires epsilon ledger")
    if len(eps) < len(hops):
        raise ValueError("epsilon rows fewer than hops")
    for h in hops:
        for key in ("hop_id", "law_id", "backend", "verdict"):
            if key not in h:
                raise ValueError(f"hop missing {key}")
    for e in eps:
        for key in ("hop_id", "epsilon_name", "measured"):
            if key not in e:
                raise ValueError(f"epsilon missing {key}")


def write_state_bus(bus: UniverseStateBus, path: Path) -> UniverseStateBus:
    validate_state_bus(bus)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bus.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return bus
