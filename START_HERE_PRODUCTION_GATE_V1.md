# Start here — Production Gate (engineer)

**Status:** OPEN · not product_ready · not MEASURED  
**Canon:** `docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`

---

## 30 seconds

**Problem:** teams ship autonomy / robot / mission claims that go green without a Dual world, a sealed refuse bit, or named honesty.

**HA ritual:** before production — **Dual · sealed receipt · named ε · refuse**.

**Not this:** field MEASURED · OTP ASIC · “NASA certified” sticker.

---

## One command

```text
# once — five bins (not two):
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
| `sealed_in_ha_runtime=true` | OS lives in HA Dual, not Cursor |
| named `epsilon` on honesty | no soft-mint label upgrade |
| stranger kit reverify | receipts readable outside desk |

---

## Why you care (any level)

Without this hour you still build.  
With it you get a **stranger-reproducible refuse** — the cheap answer to “will this pass before we spend the week?”

If HA disappeared tomorrow, you would spend that week guessing. That gap is the product.

---

## Honesty

| We show | We do not claim |
|---------|-----------------|
| Dual + Rust gate + kernel seal + named ε | SPX/NASA adoption |
| Soft≠OTP · desk≠field | product_ready |

## One ask

Run `ha-production-gate`. Send the receipt or the first FAIL line.
