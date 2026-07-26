"""R_{3,0,1} CGA Cayley table — 32-blade (5D null-plane metric) · phase-2 gold."""
from __future__ import annotations

from dataclasses import dataclass

# Basis: e0 (null), e1,e2,e3 spatial (+1), e_inf (null) — bitmask order e0..e4
N_DIM = 5
METRIC_SQ = (0, 1, 1, 1, 0)
BLADE_COUNT = 32
BLADES = list(range(BLADE_COUNT))

BASIS_NAMES = ("e0", "e1", "e2", "e3", "e_inf")


def blade_name(mask: int) -> str:
    if mask == 0:
        return "s"
    parts = [BASIS_NAMES[i] for i in range(N_DIM) if (mask >> i) & 1]
    return "e" + "".join(p[1:] if p.startswith("e") else p for p in parts).replace("einf", "inf")


def _bit_index(lsb: int) -> int:
    return (lsb.bit_length() - 1) if lsb else 0


def blade_mul(a: int, b: int) -> tuple[int, int]:
    """Geometric product on blade bitmasks — metric (0,+,+,+,0)."""
    sign = 1
    common = a & b
    while common:
        lsb = common & -common
        m = METRIC_SQ[_bit_index(lsb)]
        if m:
            sign *= m
        common ^= lsb
    a_bits = [(a >> i) & 1 for i in range(N_DIM)]
    b_bits = [(b >> i) & 1 for i in range(N_DIM)]
    seq = [i for i in range(N_DIM) if a_bits[i]] + [i for i in range(N_DIM) if b_bits[i]]
    inv = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j])
    if inv % 2:
        sign *= -1
    return sign, a ^ b


def cayley_terms() -> dict[int, list[tuple[int, int, int]]]:
    terms: dict[int, list[tuple[int, int, int]]] = {k: [] for k in range(BLADE_COUNT)}
    for i in range(BLADE_COUNT):
        for j in range(BLADE_COUNT):
            sign, out = blade_mul(i, j)
            terms[out].append((i, j, sign))
    return terms


@dataclass(frozen=True)
class Cga32MulStats:
    mul_terms: int
    add_terms: int
    unique_ij_pairs: int

    def to_dict(self) -> dict:
        return {
            "mul_terms": self.mul_terms,
            "add_terms": self.add_terms,
            "unique_ij_pairs": self.unique_ij_pairs,
            "blade_count": BLADE_COUNT,
            "metric": "R_3_0_1_null_plane",
        }


def mul_stats() -> Cga32MulStats:
    terms = cayley_terms()
    active = [k for k in range(BLADE_COUNT) if terms[k]]
    mul_terms = sum(len(terms[k]) for k in active)
    add_terms = sum(max(0, len(terms[k]) - 1) for k in active)
    pairs: set[tuple[int, int]] = set()
    for k in active:
        for i, j, _ in terms[k]:
            pairs.add((i, j))
    return Cga32MulStats(mul_terms=mul_terms, add_terms=add_terms, unique_ij_pairs=len(pairs))


def export_mul_table() -> dict:
    terms = cayley_terms()
    stats = mul_stats()
    return {
        "algebra": "R_3_0_1_CGA",
        "blade_count": BLADE_COUNT,
        "metric_sq": list(METRIC_SQ),
        "stats": stats.to_dict(),
        "terms": {str(k): terms[k] for k in range(BLADE_COUNT) if terms[k]},
    }
