"""Generate CIRCT hw.comb MLIR for clifford geo_prod Cayley graph (T4 emit)."""
from __future__ import annotations

from pathlib import Path

from scripts.chip.clifford_cayley_v0 import cayley_terms

_OUT = Path(__file__).resolve().parents[2] / "mlir" / "clifford" / "lower" / "geo_prod_cayley_hw.mlir"


def _lane_extract(var: str, lane: int) -> str:
    lo = lane * 16
    ssa = f"%{var}"
    return f"{ssa}_l{lane} = comb.extract {ssa} from {lo} : (i128) -> i16"


def emit_module_lines() -> list[str]:
    terms = cayley_terms()
    lines = [
        "// Generated: python scripts/chip/gen_clifford_geo_prod_circt_mlir_v1.py",
        "hw.module @clifford_geo_prod_circt_v0(",
        "    in %a: i128,",
        "    in %b: i128,",
        "    out r: i128",
        ") {",
        "  %mask = hw.constant -1 : i16",
    ]
    for lane in range(8):
        lines.append(f"  {_lane_extract('a', lane)}")
        lines.append(f"  {_lane_extract('b', lane)}")

    mul_cache: dict[tuple[int, int], str] = {}
    for k in range(8):
        for i, j, _ in terms[k]:
            if (i, j) not in mul_cache:
                name = f"%mul_{i}_{j}"
                mul_cache[(i, j)] = name
                lines.append(f"  {name} = comb.mul %a_l{i}, %b_l{j} : i16")

    out_ssa: dict[int, str] = {}
    for k in range(8):
        if not terms[k]:
            lines.append(f"  %out{k} = hw.constant 0 : i16")
            out_ssa[k] = f"%out{k}"
            continue
        acc: str | None = None
        for idx, (i, j, sign) in enumerate(terms[k]):
            term = mul_cache[(i, j)]
            if sign < 0:
                neg = f"%neg_{k}_{idx}"
                lines.append(f"  {neg} = comb.xor {term}, %mask : i16")
                term = neg
            if acc is None:
                acc = term
            else:
                nacc = f"%acc_{k}_{idx}"
                lines.append(f"  {nacc} = comb.add {acc}, {term} : i16")
                acc = nacc
        out_ssa[k] = acc or f"%out{k}"

    packed = out_ssa[0]
    for lane in range(1, 8):
        n = f"%pack_{lane}"
        hi = out_ssa[lane]
        # infer width from packed ssa name heuristic — chain concat MSB..LSB
        if lane == 1:
            lines.append(f"  {n} = comb.concat {hi}, {packed} : i16, i16")
        else:
            lines.append(f"  {n} = comb.concat {hi}, {packed} : i16, i{lane * 16}")
        packed = n
    lines.append(f"  hw.output {packed} : i128")
    lines.append("}")
    return lines


def main() -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text("\n".join(emit_module_lines()) + "\n", encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
