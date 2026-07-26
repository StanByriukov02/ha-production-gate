"""F1 · fidelity contract — region tags + named ε per physics hop."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RegionTag(str, Enum):
    """Physics fidelity region for a hop output (PLATFORM_FOUNDATION_GATE F1)."""

    QUANTUM = "quantum"
    SEMICLASSICAL = "semiclassical"
    STATISTICAL = "statistical"


@dataclass
class EpsilonSlot:
    """Named error budget on a hop — must be falsifiable, not decorative."""

    name: str
    description: str
    unit: str | None = None
    bound: float | None = None
    bound_op: str | None = None  # e.g. "<", "KS<", "p99-p50"
    source_slug: str | None = None
    formula_id: str | None = None
    oracle: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PhysicsHop:
    """One federated handoff A → B with region tag and ε obligation."""

    hop_id: str
    from_stage: str
    to_stage: str
    region_tag: RegionTag
    epsilon: EpsilonSlot
    mechanism: str | None = None
    mechanism_class: str | None = None  # USE | ADAPT | INVENT

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["region_tag"] = self.region_tag.value
        d["epsilon"] = self.epsilon.to_dict()
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicsHop:
        eps = data.get("epsilon") or {}
        return cls(
            hop_id=str(data["hop_id"]),
            from_stage=str(data["from_stage"]),
            to_stage=str(data["to_stage"]),
            region_tag=RegionTag(str(data["region_tag"])),
            epsilon=EpsilonSlot(
                name=str(eps["name"]),
                description=str(eps["description"]),
                unit=eps.get("unit"),
                bound=eps.get("bound"),
                bound_op=eps.get("bound_op"),
                source_slug=eps.get("source_slug"),
                formula_id=eps.get("formula_id"),
                oracle=eps.get("oracle"),
            ),
            mechanism=data.get("mechanism"),
            mechanism_class=data.get("mechanism_class"),
        )


@dataclass
class FidelityContract:
    """Contract for one world W — semantic monolith via ε ledger, not one solver."""

    world_id: str
    hops: list[PhysicsHop] = field(default_factory=list)
    canon: str = "06_2BRAIN/DOGFOOD/chain/PLATFORM_FOUNDATION_GATE_V1.md"

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "canon": self.canon,
            "class": "foundation_SCAFFOLD",
            "hops": [h.to_dict() for h in self.hops],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FidelityContract:
        hops = [PhysicsHop.from_dict(h) for h in data.get("hops") or []]
        return cls(
            world_id=str(data["world_id"]),
            hops=hops,
            canon=str(data.get("canon") or cls.canon),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.world_id.strip():
            errors.append("world_id empty")
        ids = [h.hop_id for h in self.hops]
        if len(ids) != len(set(ids)):
            errors.append("duplicate hop_id")
        for h in self.hops:
            if not h.epsilon.name.strip():
                errors.append(f"{h.hop_id}: epsilon.name empty")
            if not h.epsilon.description.strip():
                errors.append(f"{h.hop_id}: epsilon.description empty")
            if h.epsilon.bound is not None and not h.epsilon.source_slug:
                errors.append(f"{h.hop_id}: numeric bound without source_slug")
        return errors


def w0_default_contract() -> FidelityContract:
    """W₀ vertical slice — workload → wear → ΔVth (corpus-grounded ε, no unsourced bounds)."""
    return FidelityContract(
        world_id="W0",
        hops=[
            PhysicsHop(
                hop_id="w0-h1-workload-to-stress",
                from_stage="riscv_block_workload",
                to_stage="SP_AF_symbolic",
                region_tag=RegionTag.STATISTICAL,
                mechanism_class="ADAPT",
                mechanism="LLVM/KLEE or VCD/STA trace → SP_i, AF_i (mod04 E1–E2)",
                epsilon=EpsilonSlot(
                    name="trace_to_activity_fidelity",
                    description="Symbolic/measured trace reproduces SP/AF vs reference slice on one hot node",
                    unit="falsifier",
                    bound_op="EXP-M4-01: path coverage vs stress ref",
                    source_slug="study-md2-math-kernel-mod04-wear",
                    formula_id="E1_E2",
                    oracle="ADAPT",
                ),
            ),
            PhysicsHop(
                hop_id="w0-h2-stress-to-bti",
                from_stage="SP_AF_symbolic",
                to_stage="NMP_BTI_model",
                region_tag=RegionTag.SEMICLASSICAL,
                mechanism_class="USE",
                mechanism="D4 N_G power law structure → mod04 NMP ΔV_th (Grasser cal PARK)",
                epsilon=EpsilonSlot(
                    name="bti_tail_mismatch",
                    description="ΔVth tail vs reference stress on nominal nMOS FET",
                    unit="mV",
                    bound_op="falsifier: PASS/FAIL vs guardband",
                    source_slug="study-oracle-sec-d4",
                    formula_id="N_G_D4",
                    oracle="MODEL",
                ),
            ),
            PhysicsHop(
                hop_id="w0-h3-bti-to-metric",
                from_stage="NMP_BTI_model",
                to_stage="delta_vth_guardband",
                region_tag=RegionTag.SEMICLASSICAL,
                mechanism_class="USE",
                mechanism="W₀ metric line — ΔVth vs guardband",
                epsilon=EpsilonSlot(
                    name="oracle_proxy_agreement",
                    description="Oracle mod04 and receipt/proxy agree on pass/fail",
                    unit="bool",
                    bound_op="must match",
                    source_slug="DOGFOOD_WORLD_CONTRACT_W0_V1",
                    formula_id="M_falsifier",
                    oracle="SPEC",
                ),
            ),
        ],
    )


def w_fab_default_contract() -> FidelityContract:
    """W_fab federated hops — scheduler chain EXP-M1-05."""
    return FidelityContract(
        world_id="W_fab",
        hops=[
            PhysicsHop(
                hop_id="h-fab-w0-vth0",
                from_stage="fab_seed_bank",
                to_stage="W0_device_ensemble",
                region_tag=RegionTag.STATISTICAL,
                mechanism_class="INVENT",
                mechanism="fab G2 tail → delta_vth0_offset_mv (PROXY coupling)",
                epsilon=EpsilonSlot(
                    name="fab_w0_tail_coupling",
                    description="Offset bounded vs standalone W0 ensemble p99",
                    unit="mV",
                    bound_op="falsifier: |offset| < 50 mV PROXY",
                    source_slug="TCAD_LUNDSTROM_A_PASS_AND_FEDERATED_ORACLE_V1",
                    formula_id="fab_w0_hop",
                    oracle="PROXY_STRUCTURE",
                ),
            ),
        ],
    )
