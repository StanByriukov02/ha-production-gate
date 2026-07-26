"""Generate sandwich / reverse / norm MLIR lowers (T4 iron — structural comb)."""
from __future__ import annotations

from pathlib import Path

from scripts.chip.gen_clifford_geo_prod_circt_mlir_v1 import emit_module_lines

_REPO = Path(__file__).resolve().parents[2]
_LOWER = _REPO / "mlir" / "clifford" / "lower"


def _reverse_module_lines() -> list[str]:
    lines = [
        "// Generated: python scripts/chip/gen_clifford_sandwich_norm_circt_mlir_v1.py",
        "hw.module @clifford_reverse_circt_v0(",
        "    in %a: i128,",
        "    out r: i128",
        ") {",
        "  %sign = hw.constant 32768 : i16",
    ]
    out_names: list[str] = []
    for lane in range(8):
        lo = lane * 16
        ssa = f"%a_l{lane}"
        lines.append(f"  {ssa} = comb.extract %a from {lo} : (i128) -> i16")
        if lane >= 4:
            n = f"%neg_l{lane}"
            lines.append(f"  {n} = comb.xor {ssa}, %sign : i16")
            out_ssa = n
        else:
            out_ssa = ssa
        out_names.append(out_ssa)
    packed = out_names[0]
    for lane in range(1, 8):
        n = f"%pack_r{lane}"
        if lane == 1:
            lines.append(f"  {n} = comb.concat {out_names[lane]}, {packed} : i16, i16")
        else:
            lines.append(f"  {n} = comb.concat {out_names[lane]}, {packed} : i16, i{lane * 16}")
        packed = n
    lines.append(f"  hw.output {packed} : i128")
    lines.append("}")
    return lines


def _sandwich_chain_lines() -> list[str]:
    return [
        "// Generated: python scripts/chip/gen_clifford_sandwich_norm_circt_mlir_v1.py",
        "hw.module @clifford_sandwich_gp_chain_circt_v0(",
        "    in %a: i128,",
        "    in %b: i128,",
        "    out r: i128",
        ") {",
        '  %ab = hw.instance "gp_ab" @clifford_geo_prod_circt_v0 (a: %a, b: %b) -> (r: %ab)',
        '  %ra = hw.instance "rev_a" @clifford_reverse_circt_v0 (a: %a) -> (r: %rev_a)',
        '  %ara = hw.instance "gp_ara" @clifford_geo_prod_circt_v0 (a: %ab, b: %rev_a) -> (r: %r)',
        "  hw.output %ara : i128",
        "}",
    ]


def _norm_stub_lines() -> list[str]:
    return [
        "// Generated: python scripts/chip/gen_clifford_sandwich_norm_circt_mlir_v1.py",
        "// PARK — bf16 sqrt not lowered; passthrough stub for mlir lower doc",
        "hw.module @clifford_norm_circt_stub_v0(",
        "    in %a: i128,",
        "    out r: i128",
        ") {",
        "  hw.output %a : i128",
        "}",
    ]


def main() -> None:
    _LOWER.mkdir(parents=True, exist_ok=True)
    gp = _LOWER / "geo_prod_cayley_hw.mlir"
    if not gp.is_file():
        from scripts.chip.gen_clifford_geo_prod_circt_mlir_v1 import main as gen_gp

        gen_gp()
    rev = _LOWER / "reverse_hw.mlir"
    rev.write_text("\n".join(_reverse_module_lines()) + "\n", encoding="utf-8")
    sandwich = _LOWER / "sandwich_gp_chain_hw.mlir"
    body = emit_module_lines() + [""] + _reverse_module_lines() + [""] + _sandwich_chain_lines()
    sandwich.write_text("\n".join(body) + "\n", encoding="utf-8")
    norm = _LOWER / "norm_stub_hw.mlir"
    norm.write_text("\n".join(_norm_stub_lines()) + "\n", encoding="utf-8")
    print(f"wrote {rev.name}, {sandwich.name}, {norm.name}")


if __name__ == "__main__":
    main()
