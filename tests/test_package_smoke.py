"""Minimal import smoke — CI truth remains `ha-production-gate`."""

from __future__ import annotations


def test_ritual_module_importable() -> None:
    from production_gate import prove_production_gate_ritual_v1 as ritual

    assert ritual.SCHEMA == "ha_production_gate_ritual_v1"
    assert callable(ritual.main)


def test_dual_socket_module_importable() -> None:
    from production_gate import dual_socket_v1 as sock

    assert sock.SCHEMA == "ha_dual_socket_v1"
    assert callable(sock.main)


def test_open_registry_diffbot_urdf_present() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    reg = root / "fixtures" / "open_registry" / "REGISTRY_v1.json"
    urdf = root / "fixtures" / "open_registry" / "urdf" / "ros_diffbot_v1.urdf"
    assert reg.is_file()
    assert urdf.is_file()


def test_owned_soils_loader() -> None:
    from pathlib import Path

    from production_gate.dual_owned_soils_v1 import SCHEMA, load_owned_soils

    root = Path(__file__).resolve().parents[1]
    pack = load_owned_soils(
        root / "fixtures" / "open_registry" / "terramech" / "dual_owned_soils_embedded_v1.json"
    )
    assert pack["schema"] == SCHEMA
    assert pack["safe_soil_id"] == "my_firm"
    assert pack["hostile_soil_id"] == "my_soft"
    assert pack["contact"]["mass_kg"] == 48.0


def test_ensure_bins_platform_id() -> None:
    from production_gate import ensure_bins_v1 as eb

    pid = eb.platform_id()
    assert "-" in pid
    assert eb.asset_name().startswith("ha-bins-")
    assert callable(eb.main)

