# Soft release — engineer Production Gate v0

**Status:** SOFT RELEASE PREP · 2026-07-26  
**Not:** product_ready · MEASURED · NASA/SPX certified · public launch  

---

## What this is

First door for an external engineer:

```text
Dual · sealed receipt · named ε · refuse
```

Command: `ha-production-gate` · pack: `results/runtime/release_engineer/LATEST/`

## Build the pack

```text
python -m dogfood_platform.release_engineer_pack_v1
# or after pip install -e .
ha-release-engineer
```

## Give the engineer

1. Link/clone + `START_HERE_PRODUCTION_GATE_V1.md`  
2. Or zip of `results/runtime/release_engineer/LATEST/`  
3. Ask one question after run: *if we shut this off tomorrow, do you lose a week of knowing?*

## PASS bar for soft release

| Check | Must |
|-------|------|
| `PRODUCTION_GATE_RITUAL_PASS` | yes |
| `F_physics_world_stack_complete` | yes |
| Board + kit present | yes |
| Soft-mint MEASURED | refused |
| Vault / journal in pack | **no** |

## After first stranger

Log: name/role (or anon) · PASS/FAIL · devastated Y/N · one quote.  
Pivot only if devastated=N.

## Marker

`RELEASE_ENGINEER_SOFT_V0` · `NO_PRIESTHOOD` · `CHEAPER_THAN_DOUBT`
