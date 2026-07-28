"""T3 — owned soils workbench: template, duplicate, reject teaching ids."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def test_template_validate_and_reject_firm_lab(tmp_path: Path) -> None:
    from production_gate.dual_owned_soils_v1 import (
        TEACHING_SOIL_IDS,
        load_owned_soils,
        make_owned_soils_template,
        parse_owned_soils_doc,
    )
    from production_gate.soils_workbench_v1 import main as soils_main

    pack = make_owned_soils_template()
    assert pack["safe"] not in TEACHING_SOIL_IDS
    assert "n" in pack["soils"][pack["safe"]]
    assert "shear" in pack["soils"][pack["safe"]]
    parse_owned_soils_doc(pack)

    bad = dict(pack)
    bad["safe"] = "firm_lab"
    bad["soils"] = dict(pack["soils"])
    bad["soils"]["firm_lab"] = bad["soils"].pop(pack["safe"])
    with pytest.raises(ValueError, match="teaching catalog"):
        parse_owned_soils_doc(bad)

    out = tmp_path / "t.json"
    assert soils_main(["template", "--out", str(out)]) == 0
    loaded = load_owned_soils(out)
    assert loaded["safe_soil_id"] == "my_firm"


def test_duplicate_soil() -> None:
    from production_gate.dual_owned_soils_v1 import duplicate_soil, make_owned_soils_template, parse_owned_soils_doc

    pack = make_owned_soils_template()
    out = duplicate_soil(pack, source_id="my_firm", new_id="my_firm_b", set_as="hostile")
    assert out["hostile"] == "my_firm_b"
    assert "my_firm_b" in out["soils"]
    parse_owned_soils_doc(out)


def test_fixtures_still_owned() -> None:
    from production_gate.dual_owned_soils_v1 import load_owned_soils

    for name in (
        "dual_owned_soils_embedded_v1.json",
        "dual_owned_soils_skidsteer_v1.json",
        "dual_owned_soils_fetch_v1.json",
        "dual_owned_soils_example_v1.json",
    ):
        pack = load_owned_soils(_ROOT / "fixtures" / "open_registry" / "terramech" / name)
        assert pack["safe_soil_id"] not in ("firm_lab", "soft_hostile")
        assert pack["hostile_soil_id"] not in ("firm_lab", "soft_hostile")


def test_reject_empty_embed_teaching() -> None:
    from production_gate.dual_owned_soils_v1 import parse_owned_soils_doc

    with pytest.raises(ValueError):
        parse_owned_soils_doc(
            {
                "schema": "ha_dual_owned_soils_v1",
                "safe": "firm_lab",
                "hostile": "soft_hostile",
                "g_mps2": 9.81,
            }
        )
