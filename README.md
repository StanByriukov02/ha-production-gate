# HA Production Gate

<p align="center">
  <strong>Soft Dual ritual:</strong> Safe must ALLOW · Hostile must REFUSE · sealed receipt · named ε.<br/>
  Rust owns the physics gate. Python is glue. Soft · not MEASURED · not HIL.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="START_HERE_PRODUCTION_GATE_V1.md">Start here</a> ·
  <a href="#honesty">Honesty</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/StanByriukov02/ha-production-gate/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="https://github.com/StanByriukov02/ha-production-gate/releases"><img src="https://img.shields.io/github/v/release/StanByriukov02/ha-production-gate?include_prereleases&sort=semver&label=version" alt="version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/StanByriukov02/ha-production-gate" alt="license"></a>
</p>

```text
./scripts/bootstrap.sh   # or scripts\bootstrap.ps1 on Windows
→ PRODUCTION_GATE_RITUAL_PASS
```

This repo ships the **CLI gate**. The screenshots below are the companion Dual desk (Hardware Atom Start here) — visual of the same Safe/Hostile idea, **not** launched by this clone.

<p align="center">
  <img src="docs/assets/hero-world.png" alt="Companion desk — Dual Hostile sinkage">
</p>

---

## What you get

| Output | Meaning |
|--------|---------|
| Safe ALLOW | teaching Dual: claim may proceed in Safe |
| Hostile REFUSE | same stack denies in Hostile |
| Named `epsilon` | honesty labels cannot be soft-upgraded |
| Kit outside repo tree | Dual JSON + board staged under TEMP on this machine |
| Rust `ha-physics-gate` | Bekker / gate boolean oracle — no pure-Python fallback |

Not included yet: field MEASURED, silicon OTP, ROS/Gazebo bridge, HIL lab, external engineer sign-off.

---

## Quick start

**Needs:** Rust toolchain · Python ≥ 3.11 · C compiler (`ha_silicon_fuse`; Windows: MSVC Build Tools).  
**First cold build** can take several minutes (five release bins). CI proves the Unix path.

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Manual path (same steps the bootstrap runs):

```bash
cargo build -p ha_physics_gate --release
cargo build -p ha_silicon_fuse --release
cargo build -p ha_energy_ledger --release
cargo build -p ha_body_identity --release
cargo build -p universe_kinematic --release --bin manipulator_kinematics_step
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ha-production-gate
```

Expect: `PRODUCTION_GATE_RITUAL_PASS` · board under `results/runtime/platform_loop/`.  
Sample: [`docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md)

---

## Example board (abridged)

```text
════════════════════════════════════════════════════════════
  HA PRODUCTION GATE — Dual teaching ritual
  verdict: PRODUCTION_GATE_RITUAL_PASS

  [PASS] F_dual_safe_allow_hostile_refuse
  [PASS] F_kernel_seal_flag_present
  [PASS] F_named_epsilon_on_seal
  [PASS] F_hostile_current_refuse
  [PASS] F_physics_world_stack_complete
  [PASS] F_soft_mint_detector_alive
  [PASS] F_kit_outside_repo_reverify
  [PASS] F_ritual_entrypoint_wired
════════════════════════════════════════════════════════════
```

---

## Honesty

- Soft teaching Dual · **not** field MEASURED · soft ≠ OTP · **not** product_ready
- Python orchestrates (~dogfood); **Rust** owns Bekker / physics-gate emit
- Seal flag `sealed_in_ha_runtime` is a **receipt field**, not TPM / remote attestation
- Kit reverify is **same-machine TEMP outside the git tree** — not a second engineer on a second OS
- Language bar: GitHub counts bytes. This tree is Python-heavy glue + Rust cores — see [`.gitattributes`](.gitattributes)

---

## Docs

| Doc | Role |
|-----|------|
| [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md) | Engineer entry |
| [`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`](docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md) | Ritual canon |
| [`docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md) | Kernel honesty ladder |

---

## Soft release pack

```bash
ha-release-engineer
# stages results/runtime/release_engineer/LATEST/
```

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

See [`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).

## Maintainers

Stanislav Byriukov — Hardware Atom / Production Gate
