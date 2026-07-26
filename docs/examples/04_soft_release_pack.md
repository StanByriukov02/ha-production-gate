# Example 04 — Soft release pack

## Goal

Stage a handoff folder another engineer can open without cloning your entire workshop history.

## Steps

```bash
# 1) green ritual
ha-production-gate

# 2) pack
ha-release-engineer

# 3) inspect
ls results/runtime/release_engineer/LATEST/
```

## Typical contents

- `HOW_TO_RUN.md` — cold path from **this** `ha-production-gate` clone
- Board / ritual artifacts
- `kit/` — Dual JSON + engineer README
- Manifest JSON with honesty flags (`not_measured`, soft release, …)

## Reviewer checklist

1. Open `HOW_TO_RUN.md` — does it point at this public repo (not a private tree name)?
2. Open kit Dual files — Safe allow / Hostile refuse?
3. Confirm honesty still says soft / not MEASURED

Next: [05_no_python_gate_fallback.md](05_no_python_gate_fallback.md)
