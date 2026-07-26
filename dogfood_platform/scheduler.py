"""F2 · federated scheduler shell — chain stages with logged I/O (mock OK)."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dogfood_platform.fidelity import RegionTag

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = _REPO / "results" / "platform_bpass" / "runs"

StageFn = Callable[[dict[str, Any]], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class StageSpec:
    """One physics stage in a federated chain — not a monolith solver."""

    stage_id: str
    hop_id: str
    from_stage: str
    to_stage: str
    region_tag: RegionTag
    run: StageFn


@dataclass
class StageLogEntry:
    order: int
    stage_id: str
    hop_id: str
    from_stage: str
    to_stage: str
    region_tag: str
    input_artifact: str
    output_artifact: str
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChainRun:
    """Receipt of one scheduler execution — viewport reads state.json later."""

    run_id: str
    world_id: str
    started_at: str
    finished_at: str
    stages: list[StageLogEntry] = field(default_factory=list)
    state_artifact: str = ""
    io_log_artifact: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "world_id": self.world_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stages": [s.to_dict() for s in self.stages],
            "state_artifact": self.state_artifact,
            "io_log_artifact": self.io_log_artifact,
        }


class SchedulerShell:
    """Chain ≥2 physics stages in one process · log every handoff."""

    def __init__(self, runs_root: Path | None = None) -> None:
        self.runs_root = runs_root or DEFAULT_RUNS
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def run_chain(
        self,
        world_id: str,
        stages: list[StageSpec],
        initial_input: dict[str, Any],
        *,
        run_id: str | None = None,
    ) -> ChainRun:
        if len(stages) < 2:
            raise ValueError("F2 requires at least two chained stages")
        rid = run_id or f"w0-mock-{uuid.uuid4().hex[:12]}"
        run_dir = self.runs_root / rid
        run_dir.mkdir(parents=True, exist_ok=False)

        started = _now()
        payload = dict(initial_input)
        log_entries: list[StageLogEntry] = []
        io_log_path = run_dir / "io_log.jsonl"

        with io_log_path.open("w", encoding="utf-8") as log_f:
            for order, spec in enumerate(stages, start=1):
                in_name = f"stage_{order:02d}_in.json"
                out_name = f"stage_{order:02d}_out.json"
                in_path = run_dir / in_name
                out_path = run_dir / out_name
                in_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                out_payload = spec.run(payload)
                out_path.write_text(
                    json.dumps(out_payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                ts = _now()
                entry = StageLogEntry(
                    order=order,
                    stage_id=spec.stage_id,
                    hop_id=spec.hop_id,
                    from_stage=spec.from_stage,
                    to_stage=spec.to_stage,
                    region_tag=spec.region_tag.value,
                    input_artifact=str(in_path.relative_to(_REPO)).replace("\\", "/"),
                    output_artifact=str(out_path.relative_to(_REPO)).replace("\\", "/"),
                    ts=ts,
                )
                log_entries.append(entry)
                log_f.write(
                    json.dumps(
                        {
                            **entry.to_dict(),
                            "input": payload,
                            "output": out_payload,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                payload = out_payload

        state_path = run_dir / "state.json"
        state = {
            "run_id": rid,
            "world_id": world_id,
            "updated_at": _now(),
            "stages_executed": [s.stage_id for s in log_entries],
            "final": payload,
            "fidelity_hops": [s.hop_id for s in log_entries],
        }
        state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        manifest_path = run_dir / "run_manifest.json"
        finished = _now()
        run = ChainRun(
            run_id=rid,
            world_id=world_id,
            started_at=started,
            finished_at=finished,
            stages=log_entries,
            state_artifact=str(state_path.relative_to(_REPO)).replace("\\", "/"),
            io_log_artifact=str(io_log_path.relative_to(_REPO)).replace("\\", "/"),
        )
        manifest_path.write_text(
            json.dumps(run.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return run

    def latest_run_dir(self, world_id: str | None = None) -> Path | None:
        dirs = sorted(
            (p for p in self.runs_root.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for d in dirs:
            manifest = d / "run_manifest.json"
            if not manifest.is_file():
                continue
            if world_id is None:
                return d
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("world_id") == world_id:
                return d
        return None

    def validate_f2(self, world_id: str = "W0") -> list[str]:
        errors: list[str] = []
        run_dir = self.latest_run_dir(world_id)
        if run_dir is None:
            errors.append(f"no run for world_id={world_id}")
            return errors
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        stages = manifest.get("stages") or []
        if len(stages) < 2:
            errors.append("chain has fewer than 2 stages")
        for rel in ("io_log_artifact", "state_artifact"):
            path = _REPO / str(manifest.get(rel) or "")
            if not path.is_file():
                errors.append(f"missing {rel}")
        return errors
