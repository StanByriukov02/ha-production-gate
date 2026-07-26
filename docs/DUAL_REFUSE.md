# Dual refuse — method (public)

**Claim class:** soft teaching referee — not field MEASURED  
**Repo:** https://github.com/StanByriukov02/ha-production-gate

## Claim

Before treating a physics claim as green on a teaching stack:

1. **Safe** → physics gate **ALLOW**
2. **Hostile** → same gate **REFUSE** (`current_allowed=false`)
3. Decision from **Rust** `ha-physics-gate` (emit/validate) — no pure-Python PASS if the bin is missing
4. Named honesty (`ε`) on the receipt
5. Dual JSON available after the run (kit outside the git tree on this machine)

If Hostile still allows, the ritual fails.

## Run

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh    # Windows: .\scripts\bootstrap.ps1
```

Expect `PRODUCTION_GATE_RITUAL_PASS`. Board + examples: [`examples/`](examples/).

## Honesty

Soft teaching Dual · not field MEASURED · not HIL · not OTP · seal flag on receipt ≠ TPM · CLI ritual (README desk image is companion visual only).

## Falsifiers

See the board after a run, or [`examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](examples/PRODUCTION_GATE_BOARD_SAMPLE.md).
