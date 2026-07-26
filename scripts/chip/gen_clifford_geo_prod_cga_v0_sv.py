"""Generate clifford_geo_prod_cga_v0.v — CGA motor = dual quaternion product (T5 iron fork)."""
from __future__ import annotations

from pathlib import Path

_OUT = Path(__file__).resolve().parents[2] / "fixtures" / "chip" / "clifford_geo_prod_cga_v0.v"


def main() -> None:
    lines = [
        "// CGA motor geo_prod v0 — dual quaternion multiply on motor128 (T5 fork)",
        "// Regenerate: python scripts/chip/gen_clifford_geo_prod_cga_v0_sv.py",
        "// Layout: lanes0..3 Qr(w,x,y,z) · lanes4..7 Qd(w,x,y,z) — NOT Cl(3,0) Cayley",
        "`include \"clifford_alu_v0_pkg.vh\"",
        "`include \"clifford_bf16_ops_v0.vh\"",
        "",
        "module clifford_geo_prod_cga_v0 (",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] a,",
        "    input  wire [`CLIFFORD_MOTOR_W-1:0] b,",
        "    output reg  [`CLIFFORD_MOTOR_W-1:0] r",
        ");",
        "",
        "  function automatic void quat_mul_real(",
        "    input real aw, input real ax, input real ay, input real az,",
        "    input real bw, input real bx, input real by, input real bz,",
        "    output real ow, output real ox, output real oy, output real oz",
        "  );",
        "    begin",
        "      ow = aw*bw - ax*bx - ay*by - az*bz;",
        "      ox = aw*bx + ax*bw + ay*bz - az*by;",
        "      oy = aw*by - ax*bz + ay*bw + az*bx;",
        "      oz = aw*bz + ax*by - ay*bx + az*bw;",
        "    end",
        "  endfunction",
        "",
        "  real arw, arx, ary, arz, adw, adx, ady, adz;",
        "  real brw, brx, bry, brz, bdw, bdx, bdy, bdz;",
        "  real rw, rx, ry, rz, dw, dx, dy, dz;",
        "  real trw, trx, try_, trz, tdw, tdx, tdy, tdz;",
        "",
        "  always @(*) begin",
        "    arw = bf16_to_real(blade_bf16_0(a)); arx = bf16_to_real(blade_bf16_1(a));",
        "    ary = bf16_to_real(blade_bf16_2(a)); arz = bf16_to_real(blade_bf16_3(a));",
        "    adw = bf16_to_real(blade_bf16_4(a)); adx = bf16_to_real(blade_bf16_5(a));",
        "    ady = bf16_to_real(blade_bf16_6(a)); adz = bf16_to_real(blade_bf16_7(a));",
        "    brw = bf16_to_real(blade_bf16_0(b)); brx = bf16_to_real(blade_bf16_1(b));",
        "    bry = bf16_to_real(blade_bf16_2(b)); brz = bf16_to_real(blade_bf16_3(b));",
        "    bdw = bf16_to_real(blade_bf16_4(b)); bdx = bf16_to_real(blade_bf16_5(b));",
        "    bdy = bf16_to_real(blade_bf16_6(b)); bdz = bf16_to_real(blade_bf16_7(b));",
        "    quat_mul_real(arw, arx, ary, arz, brw, brx, bry, brz, rw, rx, ry, rz);",
        "    quat_mul_real(arw, arx, ary, arz, bdw, bdx, bdy, bdz, tdw, tdx, tdy, tdz);",
        "    quat_mul_real(adw, adx, ady, adz, brw, brx, bry, brz, trw, trx, try_, trz);",
        "    dw = tdw + trw; dx = tdx + trx; dy = tdy + try_; dz = tdz + trz;",
        "    r = {",
        "      real_to_bf16(dz), real_to_bf16(dy), real_to_bf16(dx), real_to_bf16(dw),",
        "      real_to_bf16(rz), real_to_bf16(ry), real_to_bf16(rx), real_to_bf16(rw)",
        "    };",
        "  end",
        "endmodule",
        "",
    ]
    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
