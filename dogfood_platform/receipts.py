"""F5 · platform B-pass receipt store — json + companion md pattern."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_STORE = _REPO / "results" / "platform_bpass"

EXPERIMENT_ID_RE = re.compile(r"^EXP-M[0-9]+-[0-9]{2}$|^FOUNDATION-[A-Z0-9-]+$")
STATUS_VALUES = frozenset({"SPEC", "READY", "RUN", "PASS", "FAIL"})


@dataclass
class ExperimentReceipt:
    """One B-pass experiment row — id maps to falsifier (F5)."""

    experiment_id: str
    status: str
    world_id: str
    falsifier: str
    question: str
    ts: str = field(default_factory=lambda: _now())
    route_step: int | None = None
    prereq: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    canon_links: list[str] = field(default_factory=list)
    fidelity_hop_ids: list[str] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentReceipt:
        return cls(
            experiment_id=str(data["experiment_id"]),
            status=str(data["status"]),
            world_id=str(data["world_id"]),
            falsifier=str(data["falsifier"]),
            question=str(data["question"]),
            ts=str(data.get("ts") or _now()),
            route_step=data.get("route_step"),
            prereq=list(data.get("prereq") or []),
            artifacts=list(data.get("artifacts") or []),
            canon_links=list(data.get("canon_links") or []),
            fidelity_hop_ids=list(data.get("fidelity_hop_ids") or []),
            notes=data.get("notes"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not EXPERIMENT_ID_RE.match(self.experiment_id):
            errors.append(f"experiment_id format: {self.experiment_id!r}")
        if self.status not in STATUS_VALUES:
            errors.append(f"status must be one of {sorted(STATUS_VALUES)}")
        if not self.falsifier.strip():
            errors.append("falsifier empty")
        if not self.question.strip():
            errors.append("question empty")
        if not self.world_id.strip():
            errors.append("world_id empty")
        return errors


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md_companion(receipt: ExperimentReceipt) -> str:
    lines = [
        f"# {receipt.experiment_id}",
        "",
        f"**Status:** {receipt.status}  ",
        f"**World:** {receipt.world_id}  ",
        f"**Updated:** {receipt.ts}",
        "",
        "## Question",
        "",
        receipt.question,
        "",
        "## Falsifier",
        "",
        receipt.falsifier,
        "",
    ]
    if receipt.prereq:
        lines.extend(["## Prereq", "", *[f"- {p}" for p in receipt.prereq], ""])
    if receipt.fidelity_hop_ids:
        lines.extend(
            ["## Fidelity hops", "", *[f"- `{h}`" for h in receipt.fidelity_hop_ids], ""]
        )
    if receipt.canon_links:
        lines.extend(["## Canon", "", *[f"- {c}" for c in receipt.canon_links], ""])
    if receipt.artifacts:
        lines.extend(["## Artifacts", "", *[f"- `{a}`" for a in receipt.artifacts], ""])
    if receipt.notes:
        lines.extend(["## Notes", "", receipt.notes, ""])
    return "\n".join(lines)


class ReceiptStore:
    """Filesystem store under results/platform_bpass/."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_STORE
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "_index.json"

    def receipt_path(self, experiment_id: str) -> Path:
        safe = experiment_id.replace("/", "_")
        return self.root / f"{safe}.json"

    def md_path(self, experiment_id: str) -> Path:
        safe = experiment_id.replace("/", "_")
        return self.root / f"{safe}.md"

    def write(self, receipt: ExperimentReceipt, *, overwrite: bool = False) -> Path:
        errors = receipt.validate()
        if errors:
            raise ValueError("; ".join(errors))
        path = self.receipt_path(receipt.experiment_id)
        if path.exists() and not overwrite:
            raise FileExistsError(path)
        payload = receipt.to_dict()
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.md_path(receipt.experiment_id).write_text(
            _md_companion(receipt), encoding="utf-8"
        )
        self._update_index(receipt.experiment_id, path.name)
        return path

    def read(self, experiment_id: str) -> ExperimentReceipt:
        data = json.loads(self.receipt_path(experiment_id).read_text(encoding="utf-8"))
        return ExperimentReceipt.from_dict(data)

    def list_ids(self) -> list[str]:
        if not self.index_path.is_file():
            return sorted(p.stem for p in self.root.glob("*.json") if p.name != "_index.json")
        idx = json.loads(self.index_path.read_text(encoding="utf-8"))
        return list(idx.get("experiments") or [])

    def validate_all(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for eid in self.list_ids():
            try:
                errs = self.read(eid).validate()
            except Exception as exc:  # noqa: BLE001 — aggregate validation report
                errs = [str(exc)]
            if errs:
                out[eid] = errs
        return out

    def _update_index(self, experiment_id: str, filename: str) -> None:
        idx: dict[str, Any] = {"version": 1, "updated_at": _now(), "experiments": {}}
        if self.index_path.is_file():
            idx = json.loads(self.index_path.read_text(encoding="utf-8"))
            idx.setdefault("experiments", {})
        idx["updated_at"] = _now()
        idx["experiments"][experiment_id] = {
            "json": filename,
            "md": filename.replace(".json", ".md"),
        }
        self.index_path.write_text(
            json.dumps(idx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
