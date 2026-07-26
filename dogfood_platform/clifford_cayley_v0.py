"""Cl(3,0) spatial Cayley table — shared gold for oracle, SV gen, mul graph (T1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

BLADES = [0b000, 0b001, 0b010, 0b100, 0b011, 0b110, 0b101, 0b111]
BLADE_NAMES = ("s", "e1", "e2", "e3", "e12", "e23", "e31", "e123")

# Cl(3,0) spatial PGA v0: e1² = e2² = e3² = +1 · null plane e0 PARK P2.1
METRIC_SQ = (1, 1, 1)

# Even-grade motor slots (scalar + bivectors) — typical rigid rotor encoding
EVEN_MOTOR_INDICES = (0, 4, 5, 6)


def _bit_index(lsb: int) -> int:
    return (lsb.bit_length() - 1) if lsb else 0


def blade_mul(a: int, b: int) -> tuple[int, int]:
    sign = 1
    common = a & b
    while common:
        lsb = common & -common
        sign *= METRIC_SQ[_bit_index(lsb)]
        common ^= lsb
    a_bits = [(a >> i) & 1 for i in range(3)]
    b_bits = [(b >> i) & 1 for i in range(3)]
    seq = [i for i in range(3) if a_bits[i]] + [i for i in range(3) if b_bits[i]]
    inv = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j])
    if inv % 2:
        sign *= -1
    return sign, a ^ b


def cayley_terms() -> dict[int, list[tuple[int, int, int]]]:
    """Full 8-blade geometric product accumulator terms per output blade index."""
    terms: dict[int, list[tuple[int, int, int]]] = {k: [] for k in range(8)}
    for i in range(8):
        for j in range(8):
            sign, blade = blade_mul(BLADES[i], BLADES[j])
            k = BLADES.index(blade)
            terms[k].append((i, j, sign))
    return terms


def filter_terms(
    terms: dict[int, list[tuple[int, int, int]]],
    *,
    input_indices: Iterable[int] | None = None,
    output_indices: Iterable[int] | None = None,
) -> dict[int, list[tuple[int, int, int]]]:
    ins = set(input_indices) if input_indices is not None else set(range(8))
    outs = set(output_indices) if output_indices is not None else set(range(8))
    out: dict[int, list[tuple[int, int, int]]] = {k: [] for k in range(8)}
    for k in range(8):
        if k not in outs:
            continue
        for i, j, s in terms[k]:
            if i in ins and j in ins:
                out[k].append((i, j, s))
    return out


def motor_motor_output_indices() -> tuple[int, ...]:
    """Output blades reachable from even×even motor multiply (algebraic closure)."""
    terms = cayley_terms()
    filtered = filter_terms(terms, input_indices=EVEN_MOTOR_INDICES)
    return tuple(k for k in range(8) if filtered[k])


@dataclass(frozen=True)
class MulGraphStats:
    graph_id: str
    mul_terms: int
    add_terms: int
    unique_ij_pairs: int
    output_blades_active: int

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "mul_terms": self.mul_terms,
            "add_terms": self.add_terms,
            "unique_ij_pairs": self.unique_ij_pairs,
            "output_blades_active": self.output_blades_active,
        }


def stats_for_terms(terms: dict[int, list[tuple[int, int, int]]], graph_id: str) -> MulGraphStats:
    active = [k for k in range(8) if terms[k]]
    mul_terms = sum(len(terms[k]) for k in active)
    add_terms = sum(max(0, len(terms[k]) - 1) for k in active)
    pairs: set[tuple[int, int]] = set()
    for k in active:
        for i, j, _ in terms[k]:
            pairs.add((i, j))
    return MulGraphStats(
        graph_id=graph_id,
        mul_terms=mul_terms,
        add_terms=add_terms,
        unique_ij_pairs=len(pairs),
        output_blades_active=len(active),
    )


def build_graph_catalog() -> dict[str, MulGraphStats]:
    full = cayley_terms()
    even_in = filter_terms(full, input_indices=EVEN_MOTOR_INDICES)
    motor_out = motor_motor_output_indices()
    even_motor = filter_terms(full, input_indices=EVEN_MOTOR_INDICES, output_indices=motor_out)

    # CSE: one physical mul per unique (i,j) feeding all outputs
    pairs_all: set[tuple[int, int]] = set()
    for k in range(8):
        for i, j, _ in full[k]:
            pairs_all.add((i, j))
    cse_mul = len(pairs_all)
    cse_add = sum(max(0, len(full[k]) - 1) for k in range(8) if full[k])

    catalog = {
        "full_8blade_rtl": stats_for_terms(full, "full_8blade_rtl"),
        "even_input_only": stats_for_terms(even_in, "even_input_only"),
        "even_motor_closed": stats_for_terms(even_motor, "even_motor_closed"),
    }
    catalog["full_8blade_cse_unique_ij"] = MulGraphStats(
        graph_id="full_8blade_cse_unique_ij",
        mul_terms=cse_mul,
        add_terms=cse_add,
        unique_ij_pairs=cse_mul,
        output_blades_active=8,
    )
    return catalog


def matmul_4x4_stats() -> MulGraphStats:
    return MulGraphStats(
        graph_id="matmul_4x4_se3",
        mul_terms=64,
        add_terms=48,
        unique_ij_pairs=64,
        output_blades_active=16,
    )


def nl_claim_48_40() -> MulGraphStats:
    return MulGraphStats(
        graph_id="nl_claim_unverified",
        mul_terms=48,
        add_terms=40,
        unique_ij_pairs=48,
        output_blades_active=-1,
    )
