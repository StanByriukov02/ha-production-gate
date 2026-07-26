# Example 02 — Reading the kit like a reviewer

## Goal

Explain to another engineer *why* Hostile refused, using only kit files (no private workshop).

## After a PASS run

```bash
cd results/runtime/production_gate_kits/LATEST
ls
# dual_safe.json
# dual_hostile.json
# PRODUCTION_GATE.json
# README_ENGINEER.md
```

## Compare the gate fields

```bash
python - <<'PY'
import json
from pathlib import Path
root = Path("results/runtime/production_gate_kits/LATEST")
for name in ("dual_safe.json", "dual_hostile.json"):
    g = json.loads((root / name).read_text(encoding="utf-8")).get("physics_gate") or {}
    print(name, {
        "physics_pass": g.get("physics_pass"),
        "current_allowed": g.get("current_allowed"),
        "schema": g.get("schema"),
    })
PY
```

**Shape you should see:**

| File | `physics_pass` | `current_allowed` |
|------|----------------|-------------------|
| `dual_safe.json` | `true` | `true` |
| `dual_hostile.json` | `false` | `false` |

## Dig one level deeper

Hostile physics blocks (storm, traverse, envelope refuse, …) live under the Dual payload. Useful reviewer questions:

1. Did Safe and Hostile use the same body preset?
2. Is `current_allowed` false only on Hostile?
3. Are named `epsilon` values present on the seal / ritual honesty?

## Board vs kit

| File | Audience |
|------|----------|
| `PRODUCTION_GATE_BOARD_LATEST.md` | Human skim |
| `PRODUCTION_GATE.json` / ritual JSON | Machine + archive |
| `dual_*.json` | Physics gate detail |

Sample board: [PRODUCTION_GATE_BOARD_SAMPLE.md](PRODUCTION_GATE_BOARD_SAMPLE.md)

Next: [03_rust_physics_gate_cli.md](03_rust_physics_gate_cli.md)
