"""Minimal import smoke — CI truth remains `ha-production-gate`."""

from __future__ import annotations


def test_ritual_module_importable() -> None:
    from dogfood_platform import prove_production_gate_ritual_v1 as ritual

    assert ritual.SCHEMA == "ha_production_gate_ritual_v1"
    assert callable(ritual.main)


def test_clifford_oracle_importable() -> None:
    from dogfood_platform import clifford_pga8_oracle_v0 as oracle

    assert callable(oracle.motor_from_blades)
