# Example 05 — No Python gate fallback

## Goal

Demonstrate fail-closed behavior when the Rust physics-gate binary is unavailable.

## Baseline

```bash
ha-production-gate
# expect PRODUCTION_GATE_RITUAL_PASS when bins exist
```

## Break the oracle path

Temporarily move the release binary off PATH / out of `target/release`:

```bash
# Unix example
mv target/release/ha-physics-gate target/release/ha-physics-gate.bak
ha-production-gate
# expect FAIL / FileNotFoundError — not a silent Python PASS
mv target/release/ha-physics-gate.bak target/release/ha-physics-gate
```

Windows PowerShell:

```powershell
Rename-Item target\release\ha-physics-gate.exe ha-physics-gate.exe.bak
ha-production-gate
Rename-Item target\release\ha-physics-gate.exe.bak ha-physics-gate.exe
```

## What “good” looks like

- Error surfaces clearly (missing bin / resolve failure)
- No forged `physics_pass=true` from a pure-Python stand-in

This is intentional: the public claim “Rust owns the gate” must hurt when the bin is gone.

Back to [examples index](README.md)
