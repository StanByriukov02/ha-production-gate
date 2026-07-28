"""T1 — URDF contact extract honesty (urdf_extract vs override vs kind)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SKID = _ROOT / "fixtures" / "open_registry" / "urdf" / "ros_skidsteer_v1.urdf"
_FETCH = _ROOT / "fixtures" / "open_registry" / "urdf" / "_external" / "fetch.urdf"


def test_extract_skid_complete() -> None:
    from production_gate.urdf_contact_extract_v1 import extract_contact_from_urdf

    ex = extract_contact_from_urdf(_SKID)
    assert ex["complete"] is True
    assert ex["mass_kg"] == pytest.approx(62.0)
    assert ex["n_contacts"] == 2.0
    assert ex["contact_width_m"] == pytest.approx(0.28)
    assert ex["contact_length_m"] == pytest.approx(0.06 * 0.35)


def test_extract_fetch_incomplete_mesh_wheels() -> None:
    from production_gate.urdf_contact_extract_v1 import extract_contact_from_urdf

    ex = extract_contact_from_urdf(_FETCH)
    assert ex["mass_kg"] is not None and ex["mass_kg"] > 50.0
    # Mesh-only wheels → no primitive pad → incomplete (honest).
    assert ex["complete"] is False
    assert ex["n_contacts"] in (None, 0.0) or len(ex["pads"]) == 0


def test_contact_from_body_urdf_extract() -> None:
    from production_gate.body_contact_geometry_v1 import contact_from_body
    from production_gate.urdf_contact_extract_v1 import extract_contact_from_urdf

    ex = extract_contact_from_urdf(_SKID)
    body = {"model_kind": "wheeled_base", "urdf_contact": ex}
    c = contact_from_body(body)
    assert c["source"] == "urdf_extract"
    assert c["mass_kg"] == pytest.approx(62.0)
    assert c["n_contacts"] == 2.0
    assert c["honesty"]["teaching_geometry"] is False


def test_contact_from_body_override_wins() -> None:
    from production_gate.body_contact_geometry_v1 import contact_from_body
    from production_gate.urdf_contact_extract_v1 import extract_contact_from_urdf

    ex = extract_contact_from_urdf(_SKID)
    body = {
        "model_kind": "wheeled_base",
        "urdf_contact": ex,
        "owned_contact": True,
        "mass_kg": 99.0,
        "n_contacts": 4.0,
        "contact_width_m": 0.07,
        "contact_length_m": 0.12,
    }
    c = contact_from_body(body)
    assert c["source"].startswith("override:")
    assert c["mass_kg"] == pytest.approx(99.0)
    assert c["n_contacts"] == 4.0


def test_attach_urdf_sets_urdf_contact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from production_gate import robot_project_desk_v1 as desk

    projects = tmp_path / "projects"
    twin = tmp_path / "twin"
    projects.mkdir()
    twin.mkdir()
    monkeypatch.setattr(desk, "_PROJECTS", projects)
    monkeypatch.setattr(desk, "_ACTIVE", projects / "_active.json")
    monkeypatch.setattr(desk, "_TWIN_ACTIVE", twin / "active.json")

    proj = desk.create_project(name="t1-extract")
    pid = str(proj["project_id"])
    rel = _SKID.relative_to(_ROOT).as_posix()
    desk.attach_body_from_urdf(
        pid,
        rel,
        root_link="base_link",
        world_id="earth_lab_open",
        model_kind="wheeled_base",
    )
    body = desk.get_project(pid)["body"]
    assert body.get("urdf_contact", {}).get("complete") is True
    from production_gate.body_contact_geometry_v1 import contact_from_body

    c = contact_from_body(body)
    assert c["source"] == "urdf_extract"
