# Start here — Production Gate (engineer)

**Status:** OPEN · soft release · physics gate first  
**Canon:** `docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`

---

## 30 seconds

**Problem:** teams ship autonomy / robot / mission claims that go green without a Dual world, a sealed refuse bit, or named honesty on the physics.

**HA ritual:** before production — **Dual · sealed receipt · named ε · refuse**.  
**Oracle:** Rust `ha-physics-gate` (and sibling bins). Python is glue.

---

## One command

```text
# once — five Rust physics bins:
cargo build -p ha_physics_gate --release
cargo build -p ha_silicon_fuse --release
cargo build -p ha_energy_ledger --release
cargo build -p ha_body_identity --release
cargo build -p universe_kinematic --release --bin manipulator_kinematics_step

pip install -e ".[smoke]"
ha-production-gate
```

Expect: `PRODUCTION_GATE_RITUAL_PASS`  
Board: `results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md`  
Kit mirror: `results/runtime/production_gate_kits/LATEST/`

| Must see | Meaning |
|----------|---------|
| Safe `physics_pass=true` | claim may proceed in Safe world |
| Hostile `physics_pass=false` | same stack refuses in Hostile |
| `sealed_in_ha_runtime=true` | OS lives in HA Dual |
| named `epsilon` on honesty | no soft-mint label upgrade |
| stranger kit reverify | receipts readable outside desk |

---

## Why you care (any level)

Without this hour you still build.  
With it you get a **stranger-reproducible physics refuse** — the cheap answer to “may this claim ship?”

If HA disappeared tomorrow, you would spend that week guessing. That gap is the product.

---

## Honesty

| We show | We do not soft-mint |
|---------|---------------------|
| Dual + Rust physics gate + kernel seal + named ε | field MEASURED · OTP · product_ready |

## One ask

Run `ha-production-gate`. Send the receipt or the first FAIL line.
