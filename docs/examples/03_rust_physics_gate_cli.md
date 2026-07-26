# Example 03 — Rust physics gate CLI

## Goal

Use the Rust oracle directly — Bekker and related thermometers — without running the full Dual ritual.

## Build

```bash
cargo build -p ha_physics_gate --release
```

Binary:

- Unix: `./target/release/ha-physics-gate`
- Windows: `.\target\release\ha-physics-gate.exe`

## Discover commands

```bash
./target/release/ha-physics-gate --help
```

You should see (among others):

```text
emit / validate
bekker-eval
bekker-roundtrip
bekker-from-z
bekker-shear
thermal-k
radiative-bc
dust-ingress
mohr-slope
multipass-rut
…
```

## Example: Bekker help

```bash
./target/release/ha-physics-gate bekker-eval --help
```

## Example: emit / validate path (shape)

The ritual uses `emit` / `validate` around `physics_gate_v1` JSON. For exploration:

```bash
./target/release/ha-physics-gate emit --help
./target/release/ha-physics-gate validate --help
```

## Why this example matters

- Shows the **oracle surface** independently of Python glue
- Lets you probe sinkage / shear / thermal slices while debugging a Hostile refuse
- Matches the README claim: Rust owns physics decisions

## Related crates in this repo

| Crate | Role |
|-------|------|
| `ha_physics_gate` | Gate + Bekker + thermometers |
| `ha_silicon_fuse` | Fuse path (C + Rust) |
| `ha_energy_ledger` | Energy ledger bin |
| `ha_body_identity` | Body identity bin |
| `universe_kinematic` | Kinematics step bin |

Next: [04_soft_release_pack.md](04_soft_release_pack.md)
