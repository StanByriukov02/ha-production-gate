# HA Production Gate

**Before you ship a robot / autonomy / mission physics claim — Dual · sealed receipt · named ε · refuse.**

[![CI](https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-yellow.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/rust-required-orange.svg)](https://www.rust-lang.org/)

Teams still go green on sim without a Dual world, a sealed refuse bit, or named honesty.
This repo is one ritual that makes the lie expensive.

```text
ha-production-gate
→ PRODUCTION_GATE_RITUAL_PASS
```

Honesty: **not MEASURED** · soft ≠ OTP · **not** product_ready · **not** NASA/SPX certified.

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
- Not a GUI app · not a twin viewer · not a cloud SaaS

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
