# HA Production Gate

## What you’re looking at

A **command-line check** for robot / autonomy physics claims.

You clone this repo, build a few Rust binaries, run one command.  
You get a **pass/fail board** plus JSON receipts — not a website, not a ROS package, not a simulator you drive by hand.

The picture below is the **companion desk UI** from the Hardware Atom workshop (same Safe/Hostile idea).  
**This clone does not open that window.** This clone runs the CLI ritual.

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#what-a-person-gets">What you get</a> ·
  <a href="#what-this-is-not">What this is not</a> ·
  <a href="START_HERE_PRODUCTION_GATE_V1.md">Start here</a>
</p>

<p align="center">
  <a href="https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/StanByriukov02/ha-production-gate/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="https://github.com/StanByriukov02/ha-production-gate/releases"><img src="https://img.shields.io/github/v/release/StanByriukov02/ha-production-gate?include_prereleases&sort=semver&label=version" alt="version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/StanByriukov02/ha-production-gate" alt="license"></a>
</p>

---

## The problem (plain)

Most stacks can print **green** in one world and never prove the same claim **fails** when the world gets worse.

This gate runs the **same** body/stack twice:

| World | Expected result |
|-------|-----------------|
| **Safe** | physics gate **ALLOW** |
| **Hostile** | physics gate **REFUSE** |

If Hostile still allows, the ritual **fails**. That refuse bit is the point.

Physics decision is computed by **Rust** (`ha-physics-gate`). Python only orchestrates.

---

## What a person gets

After a successful run (`PRODUCTION_GATE_RITUAL_PASS`) you walk away with:

| You hold | In practice |
|----------|-------------|
| A terminal board | Eight checks PASS/FAIL — Dual burn, seal flag, ε, Hostile refuse, kit re-read, … |
| JSON receipt | `results/runtime/platform_loop/PRODUCTION_GATE_RITUAL_LATEST_v1.md` + `.json` |
| Dual kit | TEMP folder outside the git tree: `dual_safe.json`, `dual_hostile.json`, board |
| A habit | “Before I talk about shipping this claim — did Safe allow and Hostile refuse?” |

**Value for a human:** a stranger-reproducible *teaching* proof that your stack can say **no** under Hostile conditions — with a receipt, not a slide.

Sample board: [`docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md)

```text
./scripts/bootstrap.sh     # Windows: .\scripts\bootstrap.ps1
→ PRODUCTION_GATE_RITUAL_PASS
```

---

## What this is not

| Not this | Why we say it |
|----------|----------------|
| Not a full robot OS / twin you install and click | CLI ritual only |
| Not ROS / Gazebo / Nav2 | No bridge in this repo yet |
| Not lab MEASURED / HIL / silicon OTP | Soft teaching Dual |
| Not “NASA/SPX certified” anything | Independent open soft release |
| Not proof soft-mint is impossible forever | Detector check + honesty labels — see falsifier names |

Status in one line: **soft · teaching Dual · not product_ready**.

---

## Companion desk (visual only)

Same Dual idea humans see in the workshop desk — Hostile sinkage, RUN TICK, etc.  
Shipped here as screenshots so you know what the ritual is *about*.

<p align="center">
  <img src="docs/assets/hero-world.png" alt="Companion desk — Dual Hostile sinkage (not launched by this clone)">
</p>

---

## Quick start

**Needs:** Rust · Python ≥ 3.11 · C compiler for `ha_silicon_fuse` (Windows: MSVC Build Tools).  
Cold build of five release bins can take several minutes. CI proves the Unix path.

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Manual equivalent:

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

---

## Example board

```text
════════════════════════════════════════════════════════════
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
════════════════════════════════════════════════════════════
```

---

## Who this is for

- You build robots / autonomy / mission physics and want a **refuse habit** with a receipt  
- You want Rust to own the gate boolean, not a Python script that can soft-mint PASS  
- You’re fine with a **soft teaching** demo before MEASURED / HIL

Skip if you need a drop-in ROS node, a GUI from `git clone`, or a lab certificate today.

---

## Honesty

- Soft teaching Dual · **not** field MEASURED · soft ≠ OTP · **not** product_ready  
- Python orchestrates; **Rust** owns Bekker / physics-gate emit  
- Seal flag on the receipt ≠ TPM / remote attestation  
- Kit reverify = TEMP **on your machine** outside the git tree — not a second engineer on a second OS yet  
- Tree is Python-heavy glue + Rust cores (GitHub language bar counts bytes)

---

## Docs

| Doc | Role |
|-----|------|
| [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md) | Short engineer entry |
| [`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`](docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md) | Ritual canon |
| [`docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md) | Honesty ladder |

## Soft release pack

```bash
ha-release-engineer
# → results/runtime/release_engineer/LATEST/
```

## Contributing / Security / License

[`CONTRIBUTING.md`](CONTRIBUTING.md) · [`SECURITY.md`](SECURITY.md) · Apache-2.0 [`LICENSE`](LICENSE)

**Maintainer:** Stanislav Byriukov — Hardware Atom / Production Gate
