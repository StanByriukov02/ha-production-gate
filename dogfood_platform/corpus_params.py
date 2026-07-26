"""Sourced physics parameters — numbers only with corpus slug + formula id.

TABU: add constants here without study-* / vault L1 cite.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorpusRef:
    slug: str
    formula_id: str
    claim: str
    oracle: str  # USE | ADAPT | MODEL | PROXY_STRUCTURE


# study-oracle-sec-d4 / ORACLE_SEC_D4 — NBTI defect generation power law
NBTI_POWER_LAW_N = CorpusRef(
    slug="study-oracle-sec-d4",
    formula_id="N_G_D4",
    claim="N_G(V_G,T,t) = A·V_G^γ·exp(-E_a/k_BT)·t^n; n≈0.17",
    oracle="USE",
)
NBTI_POWER_LAW_GAMMA = CorpusRef(
    slug="study-oracle-sec-d4",
    formula_id="N_G_D4",
    claim="γ≈5 in N_G power law",
    oracle="USE",
)
N_EXP = 0.17
GAMMA = 5.0

# MD2 mod04 L1 — activity extraction (E1–E2)
SP_FORMULA = CorpusRef(
    slug="study-md2-math-kernel-mod04-wear",
    formula_id="E1_SP",
    claim="SP_i = lim_{τ→∞} (1/τ)∫ Θ(V_i(t)-V_th) dt",
    oracle="ADAPT",
)
AF_FORMULA = CorpusRef(
    slug="study-md2-math-kernel-mod04-wear",
    formula_id="E2_AF",
    claim="AF_i = N_transitions / (2·f_clock·τ)",
    oracle="ADAPT",
)

# mod04 E3 — full ΔVth path (NMP); structure cite — numeric eval PARK until Grasser cal
DVTH_NMP = CorpusRef(
    slug="study-md2-math-kernel-mod04-wear",
    formula_id="E3_DVTH",
    claim="ΔV_th(t) = ΔV_0 Σ_j P_occ,j(t); NMP kinetics E4",
    oracle="MODEL",
)

# Goes 2011 thesis (ingested crown ON 2026-06-13) — TDDS / g(τ) ladder
GOES_NMP_SUPERPOSITION = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_EQ_4_3",
    claim="Nox(t)=Nt∫ft(t,τcap,τem)g(τcap,τem)dτcap dτem — TDDS superposition",
    oracle="USE",
)
GOES_LOGNORMAL_TAU = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_EQ_4_5",
    claim="g(τ) log-normal dispersion of trap time constants (Yang class, Goes Ch.4)",
    oracle="ADAPT",
)
GOES_TDDS_TAU_RANGE = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_FIG_1_1",
    claim="TDDS emission time map ~10^-5…10^2 s; stress to 10^4 s class",
    oracle="ADAPT",
)
GOES_TRAP_DEPTH_DVTH = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_EQ_3_25",
    claim="ΔVth,m trap-depth weighted; shallow oxide traps larger step height",
    oracle="ADAPT",
)
GOES_FOX_STRESS_SCALE = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_EQ_1_4",
    claim="s(T,Fox,s)≈s0·T²·Fox,s² — phenomenological ΔVth field scaling",
    oracle="USE",
)
GOES_STRESS_POWER_N = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_EQ_1_7",
    claim="Long stress ΔVth ~ t^n, n≈0.11 after ts0~1s",
    oracle="ADAPT",
)
GOES_STRESS_N = 0.11
GOES_STRESS_TS0_S = 1.0

# Weste Ch12 — design budget class (NOT W₀ guardband until operator binds EXP-M4-01)
GUARDBAND_REF_CLASS_MV = CorpusRef(
    slug="weste-harris-cmos-vlsi-design--ch12-Chapter_12",
    formula_id="sense_offset_budget",
    claim="Typical sense-amplifier offset budget 50 mV [Amrutur00]; NBTI affects Vt",
    oracle="PROXY_STRUCTURE",
)
GUARDBAND_REF_MV = 50.0

# W₀ contract — nominal die temperature
W0_NOMINAL_T_K = CorpusRef(
    slug="DOGFOOD_WORLD_CONTRACT_W0_V1",
    formula_id="env_T",
    claim="Die T nominal · no radiation in first run → 298.15 K (25 °C)",
    oracle="USE",
)
T_NOMINAL_K = 298.15

# radiation-effects-advanced-devices-mdpi — HCI stress ref anchor (ADAPT to mod04 BTI metric)
HCI_DVTH_ANCHOR = CorpusRef(
    slug="radiation-effects-advanced-devices-mdpi",
    formula_id="HCI_DVTH_COND1_5000S",
    claim="NMOS HCI cond1 VG=1.8V VD=2.7V: ΔVth≈173 mV after 5000 s (non-irradiated)",
    oracle="ADAPT",
)
HCI_ANCHOR_VGS_V = 1.8
HCI_ANCHOR_T_S = 5000.0
HCI_ANCHOR_DVTH_MV = 173.0

# IEC 62416-2010 via same study — space-relevant qual failure line (~10% Vth)
IEC62416_DVTH_CRITERION = CorpusRef(
    slug="radiation-effects-advanced-devices-mdpi",
    formula_id="IEC_62416_DVTH_50MV",
    claim="IEC 62416-2010: ΔVth=50 mV ≈10% Vth degradation as HCI lifetime failure criterion",
    oracle="USE",
)
W0_GUARDBAND_MV = 50.0

# G_W0_op — operating wear budget (T4 bind EXP-M4-01 2026-06-13)
# Derivation: Goes bridge 38.4444 mV (nmp_ode_receipt_v2) × 1.25 design margin
W0_GUARDBAND_OP_PREDICTED_MV = 38.4444
W0_GUARDBAND_OP_MARGIN = 1.25
W0_GUARDBAND_OP_MV = round(W0_GUARDBAND_OP_PREDICTED_MV * W0_GUARDBAND_OP_MARGIN, 2)  # 48.06

W0_GUARDBAND_OP = CorpusRef(
    slug="goes-2011-hole-trapping-nbti-thesis",
    formula_id="GOES_EQ_1_4",
    claim="G_W0_op = 1.25× Goes Fox² bridge @ W0 operating (38.44→48.06 mV) — not IEC 50 mV",
    oracle="USE",
)
G_HCI_QUAL = CorpusRef(
    slug="radiation-effects-advanced-devices-mdpi",
    formula_id="IEC_62416_DVTH_50MV",
    claim="G_HCI = 50 mV IEC qual accelerated — ref class only, not W0 operating line",
    oracle="USE",
)

# LC-2 qual passport — SAMD21RT rad-tol MCU class clock (joint controller tier)
LC2_SAMD21RT_CLOCK = CorpusRef(
    slug="study-lc2-joint-controller-fixture",
    formula_id="EMBEDDED_MCU_CLOCK_CLASS",
    claim="LC-2 qual cites Microchip SAMD21RT — 48 MHz class embedded MCU for lunar joint tier",
    oracle="ADAPT",
)
LC2_FOC_CLOCK_HZ = 48_000_000

# Rabaey — modern digital Vdd floor (operating Vgs proxy for core FET)
RABAey_VDD_CLASS = CorpusRef(
    slug="rabaey-digital-integrated-circuits--ch01-A_Historical_Perspectiv",
    formula_id="VDD_STABLE_MV",
    claim="Digital supply stable within few hundred mV; modern designs 1.2–2.5 V",
    oracle="ADAPT",
)
W0_VGS_ON_V = 1.2

# radiation-effects — measured NMOS Vth before HCI (device anchor)
HCI_VTH0_V = 0.4771
