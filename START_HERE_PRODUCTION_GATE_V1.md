# Start here — Production Gate (engineer)

**Status:** OPEN · soft teaching Dual · physics gate first  
**Canon:** `docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`

---

## 30 seconds

**Problem:** autonomy / robot claims often go green without a Dual Safe/Hostile refuse and without named honesty on the physics label.

**This repo:** soft Dual ritual — **Safe ALLOW · Hostile REFUSE · seal flag · named ε**.  
**Oracle:** Rust `ha-physics-gate`. Python is glue. Soft · not MEASURED · not HIL.

Screenshots on the README are the companion desk UI — this clone runs the **CLI**.

---

## Cold path

```text
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Or manually: build five Rust release bins → `pip install -e .` → `ha-production-gate`.

Expect: `PRODUCTION_GATE_RITUAL_PASS`  
Board: `results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md`

| Must see | Meaning |
|----------|---------|
| Safe `physics_pass=true` | teaching Safe world allows |
| Hostile `physics_pass=false` | same stack refuses in Hostile |
| Seal flag on kernel receipt | receipt field — not TPM |
| named `epsilon` | no soft label upgrade |
| kit outside repo tree | TEMP re-read on this machine |

---

## Honesty

| We show | We do not soft-mint |
|---------|---------------------|
| Dual + Rust physics gate + named ε | field MEASURED · OTP · product_ready · HIL |

## One ask

Run the bootstrap (or `ha-production-gate`). Send the receipt or the first FAIL line.
