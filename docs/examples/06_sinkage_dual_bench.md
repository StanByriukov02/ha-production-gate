# Example 06 — Sinkage Dual bench (`lunar_scout`)

## Goal

Show **one physics table** a reviewer can argue with: same body, same `g`, two soils — Safe allows, Hostile refuses. Numbers from a real `ha-production-gate` PASS, not a slide.

## Claim class

Soft teaching Dual · Bekker ON slice · **not** field MEASURED · **not** HIL · **not** NASA certified.

## Frozen receipt

[`sinkage_dual_bench_lunar_scout_v1.json`](sinkage_dual_bench_lunar_scout_v1.json)

Captured after `PRODUCTION_GATE_RITUAL_PASS` (UTC stamp inside the JSON). Re-run the ritual anytime; your kit should match this *shape*.

## Table (Bekker point sinkage)

| Lane | Soil id | `sinkage_mm` | Drawbar `N` | Compaction `Rc` `N` | Traverse feasible | Gate |
|------|---------|--------------|-------------|---------------------|-------------------|------|
| **Safe** | `lunar_firm_proxy` | **5.184** | 37.733 | 1.68 | yes | `physics_pass=true` · `current_allowed=true` |
| **Hostile** | `lunar_soft_proxy` | **135.539** | 8.919 | 51.664 | **no** | `physics_pass=false` · `current_allowed=false` |

Shared bind:

| Field | Value |
|-------|-------|
| Body | `lunar_scout` |
| `g` | `1.62` m/s² |
| Contact width `b` | `0.025` m |
| Contact area | `0.00225` m² |
| Traverse sinkage cap | `18.0` mm |
| Oracle | Rust `ha_physics_gate_bekker` |

Hostile sinkage ≫ traverse cap → `sinkage_risk=true` → gate **REFUSE**.

## Equation (oracle)

```text
p = (kc/b + k_phi) * z^n
z = (p / (kc/b + k_phi))^(1/n)
```

## Reproduce

```bash
./scripts/bootstrap.sh    # or Windows bootstrap.ps1
ha-production-gate
```

Then:

```bash
# Windows PowerShell
python -c "import json; from pathlib import Path; k=Path('results/runtime/production_gate_kits/LATEST');
for n in ('dual_safe.json','dual_hostile.json'):
 d=json.loads((k/n).read_text(encoding='utf-8')); b=d['dual_block']['physics']['bekker']; g=d['physics_gate'];
 print(n, b['soil_id'], b['sinkage_mm'], 'pass=', g['physics_pass'], 'allowed=', g['current_allowed'])"
```

## How to use this in a conversation

One sentence:

> Same `lunar_scout` contact under Moon `g`: firm proxy sinks ~5 mm and the gate allows; soft proxy sinks ~136 mm (cap 18 mm) and the gate refuses — Dual refuse, not a green-sim story.

Ask form (for someone who already knows you):

> Does this Safe/Hostile sinkage split help your community avoid shipping a traverse claim that only ever ran on firm soil?

## Honesty

- Soils are **teaching proxies** (`lunar_firm_proxy` / `lunar_soft_proxy`), not a named flight site measurement.
- Full Dual payload also carries envelope / dust / adjunct lanes — this bench isolates **Bekker sinkage → gate bits**.
- Method: [`../DUAL_REFUSE.md`](../DUAL_REFUSE.md)

Next: [01_dual_ritual_lunar_scout.md](01_dual_ritual_lunar_scout.md) · [02_reading_the_kit.md](02_reading_the_kit.md)
