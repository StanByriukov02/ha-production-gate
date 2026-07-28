"""T2 — desk run log save / list / compare."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from production_gate import desk_run_log_v1 as log

    d = tmp_path / "desk_runs"
    monkeypatch.setattr(log, "_LOG_DIR", d)
    monkeypatch.setattr(log, "_INDEX", d / "INDEX_v1.json")
    return d


def _board(**kwargs):
    base = {
        "verdict": "DUAL_SOCKET_PASS",
        "body": {"mode": "preset", "preset": "open_diffbot", "world_id": "earth_lab_open"},
        "contact": {
            "mass_kg": 48.0,
            "n_contacts": 4.0,
            "contact_width_m": 0.055,
            "contact_length_m": 0.09,
            "source": "kind:wheeled_base",
        },
        "soils": {"safe_id": "firm_lab", "hostile_id": "soft_hostile", "owned_path": None},
        "safe": {"sinkage_mm": 9.5, "soil_id": "firm_lab", "current_allowed": True},
        "hostile": {"sinkage_mm": 69.0, "soil_id": "soft_hostile", "current_allowed": False},
    }
    base.update(kwargs)
    return base


def test_save_list_compare(log_dir: Path) -> None:
    from production_gate import desk_run_log_v1 as log

    a = log.save_run(_board(), label="first")
    b = log.save_run(
        _board(
            verdict="DUAL_SOCKET_FAIL",
            safe={"sinkage_mm": 12.0, "soil_id": "firm_lab", "current_allowed": True},
            contact={
                "mass_kg": 62.0,
                "n_contacts": 2.0,
                "contact_width_m": 0.28,
                "contact_length_m": 0.021,
                "source": "urdf_extract",
            },
        ),
        label="second",
    )
    runs = log.list_runs()
    assert len(runs) >= 2
    assert runs[0]["id"] == b["id"]
    assert (log_dir / f"{a['id']}.json").is_file()

    cmp = log.compare_runs(a["id"], b["id"])
    assert "verdict" in cmp["diff_keys"]
    assert "safe_mm" in cmp["diff_keys"]
    assert "contact" in cmp["diff_keys"]
    assert cmp["a"]["contact"]["source"] == "kind:wheeled_base"
    assert cmp["b"]["contact"]["source"] == "urdf_extract"


def test_keep_trims(log_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from production_gate import desk_run_log_v1 as log

    monkeypatch.setattr(log, "DEFAULT_KEEP", 3)
    for i in range(5):
        log.save_run(_board(verdict=f"V{i}"))
    runs = log.list_runs()
    assert len(runs) == 3
