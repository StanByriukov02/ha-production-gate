# HA Production Gate

**Before you ship a robot / autonomy / mission physics claim — Dual · sealed receipt · named ε · refuse.**

[![CI](https://img.shields.io/github/actions/workflow/status/StanByriukov02/ha-production-gate/ci.yml?branch=main&label=CI)](https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/StanByriukov02/ha-production-gate?include_prereleases&sort=semver&label=version)](https://github.com/StanByriukov02/ha-production-gate/releases)
[![License](https://img.shields.io/github/license/StanByriukov02/ha-production-gate)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/StanByriukov02/ha-production-gate)](https://github.com/StanByriukov02/ha-production-gate/commits/main)
[![Issues](https://img.shields.io/github/issues/StanByriukov02/ha-production-gate)](https://github.com/StanByriukov02/ha-production-gate/issues)

[![Python](https://img.shields.io/badge/python-3.11%2B-yellow?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-required-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Ritual](https://img.shields.io/badge/ritual-Dual%20·%20seal%20·%20ε%20·%20refuse-0ea5e9)](START_HERE_PRODUCTION_GATE_V1.md)
[![Honesty](https://img.shields.io/badge/honesty-not%20MEASURED-critical)](#what-this-is-not)

Teams still go green on sim without a Dual world, a sealed refuse bit, or named honesty.
This repo is one ritual that makes the lie expensive.

```text
ha-production-gate
→ PRODUCTION_GATE_RITUAL_PASS
```

Honesty: **not MEASURED** · soft ≠ OTP · **not** product_ready · **not** NASA/SPX certified.

---

## What it looks like

**This public repo’s core action is the CLI gate** (`ha-production-gate`).  
The screens below are the companion **Start here** desk from the Hardware Atom vertical — so you see the Dual / World / Mission surface a human actually works in (teaching desk · not MEASURED · not Isaac GT).

<p align="center">
  <img src="docs/assets/desk-world.png" alt="Start here · World — Dual Safe/Hostile sinkage bed" width="920" />
</p>

<p align="center"><sub><b>World</b> — change one condition · see policies diverge · Hostile sinkage inject on Moon field</sub></p>

<p align="center">
  <img src="docs/assets/desk-mission.png" alt="Start here · Mission — Safe vs Hostile sinkage on lunar globe" width="920" />
</p>

<p align="center"><sub><b>Mission</b> — same Dual numbers on the globe · Safe 10.7 mm vs Hostile 779.5 mm sinkage (Δ visible)</sub></p>

---

## What you get

| You see | Meaning |
|---------|---------|
| Safe world ALLOW | claim may proceed in the Safe Dual |
| Hostile world REFUSE | same stack denies in Hostile |
| `sealed_in_ha_runtime=true` | OS lives in the HA Dual, not in an IDE chat |
| Named `epsilon` | you cannot soft-mint the label upward |
| Stranger kit | receipts re-readable outside the author's desk |

**Without this gate you still can simulate.**  
What you lose: a shared, stranger-checkable **refuse bit** — a week of knowing whether the claim may ship.

---

## Quick start

**Prereqs:** Python ≥ 3.11 · Rust toolchain · C compiler (for `ha_silicon_fuse` on Windows: MSVC Build Tools)

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate

python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -e ".[smoke]"

cargo build -p ha_physics_gate --release
cargo build -p ha_silicon_fuse --release
cargo build -p ha_energy_ledger --release
cargo build -p ha_body_identity --release
cargo build -p universe_kinematic --release --bin manipulator_kinematics_step

ha-production-gate
```

Expect: `PRODUCTION_GATE_RITUAL_PASS` and a board under `results/runtime/platform_loop/`.

Sample board: [`docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md)

---

## Example board (abridged)

```text
════════════════════════════════════════════════════════════
  HA PRODUCTION GATE — before you ship
  verdict: PRODUCTION_GATE_RITUAL_PASS

  Ritual:  Dual · sealed receipt · named ε · refuse

  [PASS] F_dual_safe_allow_hostile_refuse
  [PASS] F_kernel_sealed_in_ha_runtime
  [PASS] F_named_epsilon_on_seal
  [PASS] F_hostile_current_refuse
  [PASS] F_physics_world_stack_complete
  [PASS] F_soft_mint_impossible
  [PASS] F_stranger_kit_reverify
  [PASS] F_ritual_is_one_command
════════════════════════════════════════════════════════════
```

---

## Who this is for

- Someone building a robot who needs to prove **to themselves** that a claim is allowed to ship
- Robotics / sim engineers (ROS, Gazebo, Nav2, MoveIt world)
- SPX / Tesla / new-robot-company engineers who want a pre-merge refuse habit
- People who want to **see** Dual in a desk (World / Mission screens above) — and still run the stranger-checkable CLI

One face for every level. No “simple mode for beginners / serious mode for NASA.”

---

## What this is not

- Field MEASURED physics
- OTP / ASIC tape-out proof
- “NASA certified” or SpaceX adoption
- The full Hardware Atom private workshop (chips, vault, NIW, operator journals)

Private workshop (operator): separate. This surface is the **public Production Gate** only.

---

## Docs

| Doc | Role |
|-----|------|
| [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md) | Engineer 30-second entry |
| [`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`](docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md) | Ritual canon |
| [`docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md) | Kernel honesty ladder |

---

## Soft release pack

After a local PASS:

```bash
ha-release-engineer
# stages results/runtime/release_engineer/LATEST/
```

Ask one question: *if this gate disappeared tomorrow, would you lose a week of knowing?*

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Bug reports and “I ran the gate — here’s my board” issues are welcome.

## Security

See [`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).

---

## Maintainers

Stanislav Byriukov — Hardware Atom / Production Gate

Regards,  
Stan

---

## Badge contract (why these cells exist)

Live shields beat static stickers: CI / version / last-commit / issues change when the repo is alive.  
That is a **trust heuristic** in 2026 GitHub — not magic, not a substitute for a working Quick Start.

| Keep | Skip (for this repo) |
|------|----------------------|
| CI · version · license · last commit · issues | Fake “Skills: 150” / vanity social walls |
| Honesty / ritual labels that match the product | “Works with 12 AI tools” marketing rows |
| Badges that can go **red** when broken | Always-green stickers with no backend |
