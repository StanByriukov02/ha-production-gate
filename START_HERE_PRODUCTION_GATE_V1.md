# Start here — Production Gate

## What this is

One CLI ritual. Not an app. Not ROS.

You run it → you get a **board + JSON** that says:

- **Safe** world: physics gate ALLOW  
- **Hostile** world: physics gate REFUSE  

If Hostile still allows → **FAIL**. That is the product.

Rust decides the gate. Python wires the run. Soft · not MEASURED · not HIL.

README screenshots = companion desk (workshop). **This clone does not open that UI.**

---

## What you get after PASS

1. Terminal board with eight PASS/FAIL lines  
2. `results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md`  
3. Kit under TEMP (outside the repo): Dual JSON + board  

**Human meaning:** a receipt that your stack can refuse under Hostile conditions — teaching Dual, not a lab certificate.

---

## Run

```text
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Expect: `PRODUCTION_GATE_RITUAL_PASS`

| Must see | Meaning |
|----------|---------|
| Safe `physics_pass=true` | teaching Safe allows |
| Hostile `physics_pass=false` | same stack refuses |
| named `epsilon` | honesty labels stay honest |
| kit outside repo | TEMP re-read on this machine |

---

## Honesty

| We show | We do not claim |
|---------|-----------------|
| Dual + Rust gate + receipt | MEASURED · OTP · product_ready · HIL · “certified” |

Send the board or the first FAIL line.
