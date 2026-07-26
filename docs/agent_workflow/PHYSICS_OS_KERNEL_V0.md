# PHYSICS OS KERNEL v0 — half-OS **внутри HA-физики**

**Status:** ACTIVE · **HIERARCHY TOP** · 2026-07-26  
**Who:** ты + я  
**Parents:** `LIE_MUST_COST_PHYSICALLY` · `TECHNO_INDEPENDENCE_PHYSICS_PACE_V1` · `IRON_HOP_PARK_V1` · `PROOF_TIER_LADDER_V1`  

---

## Где живёт OS (LOCKED)

**Не Cursor.** Cursor rule — только напоминалка агенту.  

**OS = runtime внутри физики HA:**

```text
robot_project_run_v1.run_project
  → embeds · energy · physics_gate (Rust) · fuse
  → seal_kernel_on_run(...)          ← ядро OS здесь
  → run receipt.physics_os_kernel
  → closed_loop.kpi.physics_os_kernel_ok
```

Каждый Dual run несёт seal. Kernel FAIL → `current_allowed=false` (os_refuse).  
Prove/depth — термометры; **исполнение** — в `run_project`.

---

## Что это

```text
закон → Rust/oracle → Dual Safe≠Hostile → gate/current → proof_tier + ε → receipt
```

Единица = ячейка (falsifier + receipt).  
Апгрейд MEASURED/OTP/CREME без снятия ε = hard fault.

---

## Hierarchy

```text
0  PRODUCTION_GATE_RITUAL (engineer surface)   ← NOW
1  PHYSICS_OS_KERNEL (inside run_project)
2  TEACHING_DUAL foundation
3  PROOF_TIER_LADDER cells
4  IRON / MEASURED / OTP / CREME / PIC / multibody
```

Primary motion = simplify ritual · not deepen packs.
---

## Contracts K0–K5

| ID | Contract |
|----|----------|
| K0 | Dual burns (когда peer Safe/Hostile есть) |
| K1 | Rust gate coherence |
| K2 | `failure_modes_clear` на gate inputs |
| K3 | soft ≠ OTP |
| K4 | ε + not_measured |
| K5 | no soft-mint |

---

## Layers

| Layer | Tech |
|-------|------|
| Dual / seal / prove | Python |
| physics ALU / gate | Rust |
| scarce | C eFUSE |
| cited ROM | JSON ON |

---

## Smoke

```text
python -m dogfood_platform.prove_physics_os_kernel_v1
# must include F_kernel_sealed_in_ha_runtime
```

## Marker

`PHYSICS_OS_KERNEL_V0` · `INSIDE_HA_RUNTIME` · `NOT_CURSOR` · `TY_PLUS_YA`
