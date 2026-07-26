"""Moon Shackleton traverse — vector mint + RTL TB (iron/cxx only)."""
from __future__ import annotations

import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_MOON = _REPO / "fixtures" / "robot" / "m_moon_shackleton_traverse_tick_stream_v1.json"
_VEC_JSON = _REPO / "fixtures" / "chip" / "clifford_moon_motion_vectors_v1.json"
_VEC_BIN = _REPO / "fixtures" / "chip" / "clifford_moon_motion_vectors_v1.bin"
_RTL_TB = _REPO / "fixtures" / "chip" / "clifford_moon_motion_rtl_tb_v0.v"
_BODY_REF_M = (0.31, 0.0, 0.21)
_THETA_SCALE = math.pi * 0.42


def _load_oracle():
    path = _REPO / "scripts" / "chip" / "clifford_pga8_oracle_v0.py"
    spec = importlib.util.spec_from_file_location("clifford_pga8_oracle_v0", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _motor_hex(coeffs: list[int]) -> str:
    w = 0
    for i, c in enumerate(coeffs):
        w |= (int(c) & 0xFFFF) << (16 * i)
    return f"{w:032x}"


def _pack_motor(coeffs: list[int]) -> bytes:
    return struct.pack("<8H", *[int(c) & 0xFFFF for c in coeffs])


def _ensure_stream() -> dict:
    if not _MOON.is_file():
        from scripts.twin.gen_moon_shackleton_traverse_tick_stream_v1 import mint_moon_traverse_stream

        return mint_moon_traverse_stream()
    return json.loads(_MOON.read_text(encoding="utf-8"))


def mint_moon_motion_vectors() -> dict:
    oracle = _load_oracle()
    stream = _ensure_stream()
    ticks_in = list(stream.get("ticks") or [])
    traverse_m = float(stream.get("traverse_m") or 22348.0)
    bx, by, bz = _BODY_REF_M
    point = oracle.motor_from_blades(e1=bx, e2=by, e3=bz)
    point_hex = _motor_hex(point)

    rows: list[dict] = []
    bin_chunks: list[bytes] = [struct.pack("<I", len(ticks_in))]
    for t in ticks_in:
        tick_i = int(t["tick"])
        meters = float(t["meters"])
        theta = (meters / traverse_m) * _THETA_SCALE
        half = theta * 0.5
        rotor = oracle.motor_from_blades(s=math.cos(half), e12=-math.sin(half))
        rev = oracle.reverse_coeffs(rotor)
        rows.append(
            {
                "tick": tick_i,
                "meters": meters,
                "path_fraction": t.get("path_fraction"),
                "zone_id": t.get("zone_id"),
                "theta_rad": theta,
                "rotor_hex": _motor_hex(rotor),
                "rev_hex": _motor_hex(rev),
                "point_hex": point_hex,
            }
        )
        bin_chunks.append(
            struct.pack("<If", tick_i, meters)
            + _pack_motor(rotor)
            + _pack_motor(point)
            + _pack_motor(rev)
        )

    doc = {
        "vector_id": "clifford_moon_motion_vectors_v1",
        "domain": "moon_shackleton",
        "traverse_m": traverse_m,
        "traverse_km": stream.get("traverse_km"),
        "body_ref_m": list(_BODY_REF_M),
        "theta_scale": _THETA_SCALE,
        "point_hex": point_hex,
        "tick_count": len(rows),
        "ticks": rows,
        "mint_role": "bf16_hex_glue_only",
        "compute_layers": ["iron_rtl_mmio", "cxx_rigid_pose", "mapped_structural"],
    }
    _VEC_JSON.parent.mkdir(parents=True, exist_ok=True)
    _VEC_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    _VEC_BIN.write_bytes(b"".join(bin_chunks))
    return doc


def write_moon_motion_rtl_tb(vectors: dict) -> Path:
    from scripts.chip.gen_clifford_world_motion_iron_v0 import write_world_motion_rtl_tb

    tb_path = write_world_motion_rtl_tb(vectors)
    text = tb_path.read_text(encoding="utf-8")
    text = text.replace("clifford_world_motion_rtl_tb_v0", "clifford_moon_motion_rtl_tb_v0")
    text = text.replace("TB_PASS rtl_world_motion", "TB_PASS rtl_moon_motion")
    text = text.replace("World motion RTL iron TB", "Moon Shackleton motion RTL iron TB")
    _RTL_TB.write_text(text, encoding="utf-8")
    return _RTL_TB


if __name__ == "__main__":
    v = mint_moon_motion_vectors()
    tb = write_moon_motion_rtl_tb(v)
    print(json.dumps({"vectors": _VEC_JSON.name, "rtl_tb": tb.name, "ticks": v["tick_count"]}))
