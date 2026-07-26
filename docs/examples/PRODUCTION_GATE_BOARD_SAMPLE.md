# HA Production Gate — engineer board (sample)

**Verdict:** `PRODUCTION_GATE_RITUAL_PASS`  
**Note:** paths below are redacted — a live run writes a TEMP kit outside the repo on your machine.

## Ritual

```text
Soft Dual teaching seal · Safe ALLOW · Hostile REFUSE · named ε
```

## Falsifiers

| id | result |
|----|--------|
| F_dual_safe_allow_hostile_refuse | PASS |
| F_kernel_seal_flag_present | PASS |
| F_named_epsilon_on_seal | PASS |
| F_hostile_current_refuse | PASS |
| F_physics_world_stack_complete | PASS |
| F_soft_mint_detector_alive | PASS |
| F_kit_outside_repo_reverify | PASS |
| F_ritual_entrypoint_wired | PASS |

## Kit

- path: `<TEMP>/ha_prod_gate_*/kit` (outside git tree, same machine)
- outside_repo: `true`
- files: `dual_safe.json, dual_hostile.json, PRODUCTION_GATE.json, README_ENGINEER.md`

## Honesty

soft teaching Dual · not MEASURED · soft≠OTP · Rust physics oracle · Python glue · seal flag ≠ TPM

## Canon

`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md` · `START_HERE_PRODUCTION_GATE_V1.md`
