# Tech note — Dual refuse Production Gate (v0)

**Status:** soft public teaching surface  
**Repo:** https://github.com/StanByriukov02/ha-production-gate  
**Claim class:** referee / refuse ritual — not field MEASURED science

---

## 1. Claim

Before treating a physics claim as shippable in a teaching stack, require:

1. **Safe** world: physics gate **ALLOW** (`physics_pass=true`, `current_allowed=true`)
2. **Hostile** world: same gate **REFUSE** (`physics_pass=false`, `current_allowed=false`)
3. Decision owned by **Rust** `ha-physics-gate` (emit/validate) — Python must not substitute a PASS if the bin is absent
4. Named honesty (`ε`) on the seal / ritual receipt
5. Dual JSON re-readable from a kit staged outside the git tree (same machine TEMP today)

If Hostile still allows, the ritual **fails**.

---

## 2. What runs

Public cold path:

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh    # Windows: .\scripts\bootstrap.ps1
```

Internally (teaching preset `lunar_scout`):

- TEMP project → attach body → `run_project(safe)` + `run_project(hostile)`
- Eight falsifiers (honest names — see board)
- Board + JSON under `results/runtime/platform_loop/`
- Kit mirror under `results/runtime/production_gate_kits/LATEST/`

Sample board: [`../examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](../examples/PRODUCTION_GATE_BOARD_SAMPLE.md)

---

## 3. Falsifiers (what “PASS” means)

| id | Meaning |
|----|---------|
| `F_dual_safe_allow_hostile_refuse` | Dual burn on teaching soils / field lane |
| `F_kernel_seal_flag_present` | Seal flag on kernel receipt (receipt field ≠ TPM) |
| `F_named_epsilon_on_seal` | ε list non-empty |
| `F_hostile_current_refuse` | Hostile `current_allowed=false` |
| `F_physics_world_stack_complete` | Hostile physics blocks present |
| `F_soft_mint_detector_alive` | Soft-mint detector responds to a synthetic probe (not “impossible forever”) |
| `F_kit_outside_repo_reverify` | TEMP kit outside git tree re-reads Dual |
| `F_ritual_entrypoint_wired` | Console script + bootstrap + START_HERE present |

---

## 4. Honesty

| We show | We do not claim |
|---------|-----------------|
| Dual Safe/Hostile refuse habit | Field MEASURED campaign |
| Rust Bekker / gate oracle | Silicon OTP / remote attestation |
| Soft teaching Dual on public fixtures | ROS/Gazebo bridge shipped |
| Seal flag on receipt | TPM / “sealed runtime” as crypto |
| Same-machine TEMP kit | Second engineer on a second OS (yet) |

Language bar / tree: Python glue is large; oracle bins are Rust. Bytes ≠ importance.

---

## 5. How to attack this note

Useful adversarial checks (welcome as issues):

1. Cold clone without author `target/` → still PASS?
2. Remove `ha-physics-gate` binary → must hard-fail
3. Force Hostile allow → ritual must FAIL
4. Point out any claim that upgrades soft → MEASURED without removing ε

---

## 6. Relation to channels 1 and 3

This note is the **method object** linked from ROS/sim posts and Show HN.  
The **strike object** is the public repo CLI — not a slide deck and not a visa ask.
