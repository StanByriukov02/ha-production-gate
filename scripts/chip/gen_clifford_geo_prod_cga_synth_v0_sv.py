"""Generate clifford_geo_prod_cga_synth_v0.v — yosys-shaped DQ motor (T5)."""
from __future__ import annotations

from pathlib import Path

_OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_geo_prod_cga_synth_v0.v"

_QUAT_COMP = (
    (
        ("aw", "bw", 1),
        ("ax", "bx", -1),
        ("ay", "by", -1),
        ("az", "bz", -1),
    ),
    (
        ("aw", "bx", 1),
        ("ax", "bw", 1),
        ("ay", "bz", -1),
        ("az", "by", 1),
    ),
    (
        ("aw", "by", -1),
        ("ax", "bz", 1),
        ("ay", "bw", 1),
        ("az", "bx", -1),
    ),
    (
        ("aw", "bz", 1),
        ("ax", "by", 1),
        ("ay", "bx", -1),
        ("az", "bw", 1),
    ),
)


def _blade(m: str, i: int) -> str:
    lo = i * 16
    return f"{m}[{lo + 15}:{lo}]"


def _emit_comp(
    lines: list[str],
    *,
    tag: str,
    comp: int,
    terms: tuple[tuple[str, str, int], ...],
    lanes: dict[str, str],
    uid: int,
) -> tuple[int, str]:
    acc = "32'h0"
    for a_key, b_key, sign in terms:
        uid += 1
        ai, bi = lanes[a_key], lanes[b_key]
        lines.append(f"  wire [31:0] f32_{tag}_{uid};")
        lines.append(f"  bf16_mul_widen_f32_v0 u_mul_{tag}_{uid} (.a({ai}), .b({bi}), .y(f32_{tag}_{uid}));")
        src = f"f32_{tag}_{uid}"
        if sign < 0:
            lines.append(f"  wire [31:0] term_{tag}_{uid};")
            lines.append(f"  assign term_{tag}_{uid} = f32_{tag}_{uid} ^ 32'h80000000;")
            src = f"term_{tag}_{uid}"
        lines.append(f"  wire [31:0] acc_{tag}_{comp}_{uid};")
        lines.append(f"  f32_add_synth_v0 u_add_{tag}_{comp}_{uid} (.a({acc}), .b({src}), .y(acc_{tag}_{comp}_{uid}));")
        acc = f"acc_{tag}_{comp}_{uid}"
    out = f"out_{tag}_{comp}"
    lines.append(f"  wire [15:0] {out};")
    lines.append(f"  f32_to_bf16_rne_v0 u_rne_{tag}_{comp} (.f({acc}), .h({out}));")
    return uid, out


def _emit_quat_mul(
    lines: list[str],
    *,
    tag: str,
    lanes: dict[str, str],
    uid: int,
) -> tuple[int, tuple[str, str, str, str]]:
    outs: list[str] = []
    for comp, terms in enumerate(_QUAT_COMP):
        uid, out = _emit_comp(lines, tag=tag, comp=comp, terms=terms, lanes=lanes, uid=uid)
        outs.append(out)
    return uid, (outs[0], outs[1], outs[2], outs[3])


def _emit_bf16_add(
    lines: list[str],
    *,
    tag: str,
    a: str,
    b: str,
    uid: int,
) -> tuple[int, str]:
    uid += 1
    lines.append(f"  wire [31:0] f32_{tag}_{uid}a;")
    lines.append(f"  bf16_mul_widen_f32_v0 u_wa_{tag}_{uid} (.a({a}), .b(16'h3f80), .y(f32_{tag}_{uid}a));")
    lines.append(f"  wire [31:0] f32_{tag}_{uid}b;")
    lines.append(f"  bf16_mul_widen_f32_v0 u_wb_{tag}_{uid} (.a({b}), .b(16'h3f80), .y(f32_{tag}_{uid}b));")
    lines.append(f"  wire [31:0] acc_{tag}_{uid};")
    lines.append(f"  f32_add_synth_v0 u_add_{tag}_{uid} (.a(f32_{tag}_{uid}a), .b(f32_{tag}_{uid}b), .y(acc_{tag}_{uid}));")
    out = f"out_{tag}_{uid}"
    lines.append(f"  wire [15:0] {out};")
    lines.append(f"  f32_to_bf16_rne_v0 u_rne_{tag}_{uid} (.f(acc_{tag}_{uid}), .h({out}));")
    return uid, out


def main() -> None:
    lines = [
        "// CGA motor geo_prod synth v0 — dual quaternion (T5 yosys probe)",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga_synth_v0_sv.py",
        '`include "clifford_alu_v0_pkg.vh"',
        "",
        "module clifford_geo_prod_cga_synth_v0 (",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] a,",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] b,",
        "    output wire [`CLIFFORD_MOTOR_W-1:0] r",
        ");",
    ]
    for m in ("a", "b"):
        for i in range(8):
            lines.append(f"  wire [15:0] {m}_bf{i} = {_blade(m, i)};")

    uid = 0
    uid, (rw, rx, ry, rz) = _emit_quat_mul(
        lines,
        tag="qr",
        lanes={
            "aw": "a_bf0",
            "ax": "a_bf1",
            "ay": "a_bf2",
            "az": "a_bf3",
            "bw": "b_bf0",
            "bx": "b_bf1",
            "by": "b_bf2",
            "bz": "b_bf3",
        },
        uid=uid,
    )
    uid, (tdw, tdx, tdy, tdz) = _emit_quat_mul(
        lines,
        tag="qd1",
        lanes={
            "aw": "a_bf0",
            "ax": "a_bf1",
            "ay": "a_bf2",
            "az": "a_bf3",
            "bw": "b_bf4",
            "bx": "b_bf5",
            "by": "b_bf6",
            "bz": "b_bf7",
        },
        uid=uid,
    )
    uid, (trw, trx, try_, trz) = _emit_quat_mul(
        lines,
        tag="qd2",
        lanes={
            "aw": "a_bf4",
            "ax": "a_bf5",
            "ay": "a_bf6",
            "az": "a_bf7",
            "bw": "b_bf0",
            "bx": "b_bf1",
            "by": "b_bf2",
            "bz": "b_bf3",
        },
        uid=uid,
    )

    qd_outs: list[str] = []
    for comp, (ta, tb) in enumerate(((tdw, trw), (tdx, trx), (tdy, try_), (tdz, trz))):
        uid, out = _emit_bf16_add(lines, tag=f"qd{comp}", a=ta, b=tb, uid=uid)
        qd_outs.append(out)

    lines.append(
        f"  assign r = {{ {qd_outs[3]}, {qd_outs[2]}, {qd_outs[1]}, {qd_outs[0]}, "
        f"{rz}, {ry}, {rx}, {rw} }};"
    )
    lines.append("endmodule")
    lines.append("")
    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
