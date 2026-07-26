"""Generate cxx CGA32 geo_prod from clifford_cga32_cayley_v1 mul table."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_OUT = _REPO / "cpp" / "clifford_soft_gp" / "src" / "cga32_geo_prod_generated.cpp"


def main() -> None:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts.chip.clifford_cga32_cayley_v1 import BLADE_COUNT, cayley_terms

    flat: list[tuple[int, int, int, int]] = []
    for out in range(BLADE_COUNT):
        for i, j, sign in cayley_terms()[out]:
            flat.append((out, i, j, sign))

    lines = [
        "// AUTO-GENERATED — do not edit",
        "// Regenerate: python scripts/chip/gen_clifford_cga32_geo_prod_cpp_v1.py",
        '#include "clifford/motor512.hpp"',
        "",
        "namespace clifford {",
        "namespace cga32_gen {",
        "",
        f"static constexpr int kTermCount = {len(flat)};",
        f"static constexpr int kBladeCount = {BLADE_COUNT};",
        "",
        "static constexpr uint8_t kOut[] = {",
        ", ".join(str(t[0]) for t in flat),
        "};",
        "static constexpr uint8_t kI[] = {",
        ", ".join(str(t[1]) for t in flat),
        "};",
        "static constexpr uint8_t kJ[] = {",
        ", ".join(str(t[2]) for t in flat),
        "};",
        "static constexpr int8_t kSign[] = {",
        ", ".join(str(t[3]) for t in flat),
        "};",
        "",
        "Motor512 geo_prod(const Motor512& a, const Motor512& b) {",
        "    float acc[kBladeCount]{};",
        "    for (int t = 0; t < kTermCount; ++t) {",
        "        const float p = bf16_to_f32(a[kI[t]]) * bf16_to_f32(b[kJ[t]]);",
        "        acc[kOut[t]] += static_cast<float>(kSign[t]) * p;",
        "    }",
        "    Motor512 out{};",
        "    for (int k = 0; k < kBladeCount; ++k) out[k] = f32_to_bf16(acc[k]);",
        "    return out;",
        "}",
        "",
        "}  // namespace cga32_gen",
        "}  // namespace clifford",
        "",
    ]
    _OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {_OUT.relative_to(_REPO)} ({len(flat)} terms)")


if __name__ == "__main__":
    main()
