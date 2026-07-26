"""Generate geo_prod synth modules — full + EX2 low/high blade slices (P5.11)."""
from __future__ import annotations

from pathlib import Path

from scripts.chip.clifford_cayley_v0 import BLADES, blade_mul, cayley_terms, filter_terms, motor_motor_output_indices

_FIX = Path(__file__).resolve().parents[2] / "fixtures" / "chip"


def _blade_slice(mvar: str, idx: int) -> str:
    lo = idx * 16
    return f"{mvar}[{lo + 15}:{lo}]"


def _blade_bf16(mvar: str, idx: int) -> str:
    return f"{mvar}_bf{idx}"


def _build_terms() -> dict[int, list[tuple[int, int, int]]]:
    return cayley_terms()


def _build_motor_terms() -> dict[int, list[tuple[int, int, int]]]:
    outs = motor_motor_output_indices()
    return filter_terms(cayley_terms(), input_indices=(0, 4, 5, 6), output_indices=outs)


def _emit_synth_module(
    *,
    module_name: str,
    blade_indices: tuple[int, ...],
    terms: dict[int, list[tuple[int, int, int]]],
    out_width: int,
    uid_start: int,
) -> tuple[list[str], int]:
    lines = [
        f"// Generated · f32 widen accumulate · P5.11 EX2 slice",
        f"// Regenerate: python scripts/chip/gen_clifford_geo_prod_synth_v0_sv.py",
        '`include "clifford_alu_v0_pkg.vh"',
        "",
        f"module {module_name} (",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] a,",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] b,",
        f"    output wire [{out_width - 1}:0] r",
        ");",
    ]
    for mvar in ("a", "b"):
        for idx in range(8):
            lines.append(f"  wire [15:0] {mvar}_bf{idx} = {_blade_slice(mvar, idx)};")
    lines.append("")

    uid = uid_start
    computed: dict[int, str] = {}
    for k in blade_indices:
        acc = "32'h0"
        for i, j, s in terms[k]:
            uid += 1
            lines.append(f"  wire [31:0] f32_{k}_{uid};")
            lines.append(
                f"  bf16_mul_widen_f32_v0 u_mul_{k}_{uid} ("
                f".a({_blade_bf16('a', i)}), .b({_blade_bf16('b', j)}), .y(f32_{k}_{uid}));"
            )
            if s < 0:
                lines.append(f"  wire [31:0] term_{k}_{uid};")
                lines.append(f"  assign term_{k}_{uid} = f32_{k}_{uid} ^ 32'h80000000;")
                src = f"term_{k}_{uid}"
            else:
                src = f"f32_{k}_{uid}"
            lines.append(f"  wire [31:0] acc{k}_{uid};")
            lines.append(
                f"  f32_add_synth_v0 u_add_{k}_{uid} (.a({acc}), .b({src}), .y(acc{k}_{uid}));"
            )
            acc = f"acc{k}_{uid}"

        lines.append(f"  wire [15:0] out{k};")
        lines.append(f"  f32_to_bf16_rne_v0 u_rne_{k} (.f({acc}), .h(out{k}));")
        computed[k] = f"out{k}"

    concat_parts: list[str] = []
    for k in range(7, -1, -1):
        if k in computed:
            concat_parts.append(computed[k])
        elif out_width == 128:
            z = f"out{k}_z"
            lines.append(f"  wire [15:0] {z} = 16'h0;")
            concat_parts.append(z)
    concat = ", ".join(concat_parts)
    lines.append(f"  assign r = {{ {concat} }};")
    lines.append("endmodule")
    lines.append("")
    return lines, uid


def main() -> None:
    terms = _build_terms()

    full_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_v0",
        blade_indices=tuple(range(8)),
        terms=terms,
        out_width=128,
        uid_start=0,
    )
    full_lines[0] = "// Clifford geo_prod synth v0 — generated · f32 widen accumulate · P5.2"
    (_FIX / "clifford_geo_prod_synth_v0.v").write_text("\n".join(full_lines), encoding="utf-8")

    low_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_low_blades_v0",
        blade_indices=(0, 1, 2, 3),
        terms=terms,
        out_width=64,
        uid_start=uid,
    )
    (_FIX / "clifford_geo_prod_synth_low_blades_v0.v").write_text("\n".join(low_lines), encoding="utf-8")

    low_lo_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_low_lo_blades_v0",
        blade_indices=(0, 1),
        terms=terms,
        out_width=32,
        uid_start=uid,
    )
    (_FIX / "clifford_geo_prod_synth_low_lo_blades_v0.v").write_text("\n".join(low_lo_lines), encoding="utf-8")

    low_hi_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_low_hi_blades_v0",
        blade_indices=(2, 3),
        terms=terms,
        out_width=32,
        uid_start=uid,
    )
    (_FIX / "clifford_geo_prod_synth_low_hi_blades_v0.v").write_text("\n".join(low_hi_lines), encoding="utf-8")

    high_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_high_blades_v0",
        blade_indices=(4, 5, 6, 7),
        terms=terms,
        out_width=64,
        uid_start=uid,
    )
    (_FIX / "clifford_geo_prod_synth_high_blades_v0.v").write_text("\n".join(high_lines), encoding="utf-8")

    high_lo_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_high_lo_blades_v0",
        blade_indices=(4, 5),
        terms=terms,
        out_width=32,
        uid_start=uid,
    )
    (_FIX / "clifford_geo_prod_synth_high_lo_blades_v0.v").write_text("\n".join(high_lo_lines), encoding="utf-8")

    high_hi_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_synth_high_hi_blades_v0",
        blade_indices=(6, 7),
        terms=terms,
        out_width=32,
        uid_start=uid,
    )
    (_FIX / "clifford_geo_prod_synth_high_hi_blades_v0.v").write_text("\n".join(high_hi_lines), encoding="utf-8")

    motor_terms = _build_motor_terms()
    motor_outs = tuple(motor_motor_output_indices())
    motor_lines, uid = _emit_synth_module(
        module_name="clifford_geo_prod_motor_synth_v0",
        blade_indices=motor_outs,
        terms=motor_terms,
        out_width=128,
        uid_start=uid,
    )
    motor_lines[0] = "// Clifford geo_prod_motor synth v0 — ROTOR_COMPOSE_ONLY even×even (T2)"
    (_FIX / "clifford_geo_prod_motor_synth_v0.v").write_text("\n".join(motor_lines), encoding="utf-8")

    print(f"wrote synth full + low/lo/hi + high/lo/hi + motor slices mul_instances={uid}")


if __name__ == "__main__":
    main()
