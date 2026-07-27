# Example 01 — Dual ritual (`lunar_scout`)

## Goal

Run the Production Gate end-to-end and obtain `PRODUCTION_GATE_RITUAL_PASS` with Safe allow + Hostile refuse.

## Stack used

- CLI: `ha-production-gate`
- Preset body: `lunar_scout`
- Oracle: Rust `ha-physics-gate`
- Glue: `production_gate/prove_production_gate_ritual_v1.py`

## Steps

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Or, if bins are already built:

```bash
source .venv/bin/activate       # Windows: .venv\Scripts\activate
ha-production-gate
```

## What the ritual does (internally)

1. Creates a TEMP project directory (outside your lasting desk state)
2. Attaches body preset `lunar_scout`
3. Ensures silicon fuse path for the project
4. Runs `run_project(..., "safe")` then `run_project(..., "hostile")`
5. Evaluates eight falsifiers
6. Stages a kit under TEMP + mirrors to `results/runtime/production_gate_kits/LATEST/`

## Expected terminal slice

```text
HA PRODUCTION GATE — soft Dual teaching ritual
verdict: PRODUCTION_GATE_RITUAL_PASS

[PASS] F_dual_safe_allow_hostile_refuse
[PASS] F_kernel_seal_flag_present
[PASS] F_named_epsilon_on_seal
[PASS] F_hostile_current_refuse
[PASS] F_physics_world_stack_complete
[PASS] F_soft_mint_detector_alive
[PASS] F_kit_outside_repo_reverify
[PASS] F_ritual_entrypoint_wired
```

## Artifacts to open next

```text
results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md
results/runtime/platform_loop/PRODUCTION_GATE_RITUAL_LATEST_v1.json
results/runtime/production_gate_kits/LATEST/dual_safe.json
results/runtime/production_gate_kits/LATEST/dual_hostile.json
```

## If it FAIL

- First FAIL id on the board is the signal — paste that line when asking for help
- Missing Rust bins → build via bootstrap
- Windows fuse link errors → MSVC Build Tools

Next: [02_reading_the_kit.md](02_reading_the_kit.md)
