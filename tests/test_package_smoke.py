"""Minimal import smoke — CI truth remains `ha-production-gate`."""

from __future__ import annotations


def test_ritual_module_importable() -> None:
    from dogfood_platform import prove_production_gate_ritual_v1 as ritual

    assert ritual.SCHEMA == "ha_production_gate_ritual_v1"
    assert callable(ritual.main)


def test_dual_socket_module_importable() -> None:
    from dogfood_platform import dual_socket_v1 as sock

    assert sock.SCHEMA == "ha_dual_socket_v1"
    assert callable(sock.main)


def test_open_registry_diffbot_urdf_present() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    reg = root / "fixtures" / "open_registry" / "REGISTRY_v1.json"
    urdf = root / "fixtures" / "open_registry" / "urdf" / "ros_diffbot_v1.urdf"
    assert reg.is_file()
    assert urdf.is_file()


def test_desk_index_present() -> None:
    from pathlib import Path

    assert (Path(__file__).resolve().parents[1] / "desk" / "index.html").is_file()
