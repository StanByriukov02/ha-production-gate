# HA Production Gate

[![CI](https://img.shields.io/github/actions/workflow/status/StanByriukov02/ha-production-gate/ci.yml?branch=main&label=CI)](https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/release/StanByriukov02/ha-production-gate?include_prereleases&sort=semver&label=version)](https://github.com/StanByriukov02/ha-production-gate/releases)
[![License](https://img.shields.io/github/license/StanByriukov02/ha-production-gate)](LICENSE)
[![Rust](https://img.shields.io/badge/physics_oracle-Rust-b45309)](crates/ha_physics_gate)
[![Python](https://img.shields.io/badge/ritual_glue-Python_3.11%2B-3776AB)](dogfood_platform)

**A Dual physics check for robot and autonomy claims.**  
Run the same stack in a **Safe** world and a **Hostile** world. Safe must **allow**. Hostile must **refuse**. You walk away with a sealed board, JSON receipts, and a kit another engineer can re-read.

Works as a CLI ritual today. The hero below is the companion Dual desk UI — same idea in visual form.

<p align="center">
  <img src="docs/assets/hero-world.png" alt="Dual desk — Hostile sinkage on lunar field">
</p>

---

## What's included

This repository ships a **runnable Production Gate surface**:

| Layer | What you get |
|-------|----------------|
| **Ritual CLI** | `ha-production-gate` — Dual Safe/Hostile run + 8 falsifiers + board |
| **Bootstrap** | `scripts/bootstrap.sh` / `scripts/bootstrap.ps1` — build bins → install → run |
| **Rust physics cores** | `ha_physics_gate`, `ha_silicon_fuse`, `ha_energy_ledger`, `ha_body_identity`, `universe_kinematic`, plus `ha_artifact_law`, `universe_scale`, `ha_iron_attestation` |
| **Bekker / terramech oracle** | `ha-physics-gate bekker-eval` and related thermometers (sinkage, shear, thermal, dust, …) |
| **Python glue** | `dogfood_platform/` — project desk, Dual run, seal, kit staging |
| **Fixtures** | Open registry / seed + teaching Dual soils for `lunar_scout` ([`fixtures/README.md`](fixtures/README.md)) |
| **Examples** | Board sample, Dual walkthrough, kit reading, Rust gate CLI — [`docs/examples/`](docs/examples/) |
| **Soft release pack** | `ha-release-engineer` → staged zip-ready folder under `results/runtime/release_engineer/LATEST/` |
| **CI** | Ubuntu job builds five bins and runs the same ritual on every `main` push |

Each successful run produces:

- Terminal board (`PRODUCTION_GATE_RITUAL_PASS` / `_FAIL`)
- `results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md`
- `results/runtime/platform_loop/PRODUCTION_GATE_RITUAL_LATEST_v1.json`
- Kit mirror: `results/runtime/production_gate_kits/LATEST/` (`dual_safe.json`, `dual_hostile.json`, …)

---

## Table of contents

- [What's included](#whats-included)
- [Why use this](#why-use-this)
- [Quick start](#quick-start)
- [Prerequisites](#prerequisites)
- [Quick examples](#quick-examples)
- [Use cases](#use-cases)
- [Repository map](#repository-map)
- [Rust physics gate CLI](#rust-physics-gate-cli)
- [Reading the outputs](#reading-the-outputs)
- [Soft release pack](#soft-release-pack)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Docs](#docs)
- [Contributing](#contributing)
- [License](#license)

---

## Why use this

### Catch “always green” physics claims

A stack that only ever runs in a friendly world can look healthy forever. Dual forces a condition change: Hostile must burn.

### Keep the oracle out of soft-mint scripts

The gate boolean is emitted/validated by **Rust** (`ha-physics-gate`). Python cannot substitute a pure-Python PASS if the bin is missing.

### Leave a receipt, not a slide

Named honesty (`ε`), Dual JSON, and a board you can paste into a review thread.

### One shared ritual

Same command for a student building a first rover claim and for an engineer checking a refuse habit before a merge conversation.

---

## Quick start

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Success looks like:

```text
verdict: PRODUCTION_GATE_RITUAL_PASS
[PASS] F_dual_safe_allow_hostile_refuse
[PASS] F_hostile_current_refuse
…
```

Short entry: [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md)

### Manual path (same steps bootstrap runs)

```bash
cargo build -p ha_physics_gate --release
cargo build -p ha_silicon_fuse --release
cargo build -p ha_energy_ledger --release
cargo build -p ha_body_identity --release
cargo build -p universe_kinematic --release --bin manipulator_kinematics_step

python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -e .
ha-production-gate
```

---

## Prerequisites

| Tool | Why |
|------|-----|
| **Rust** (stable) | Physics bins |
| **Python ≥ 3.11** | Ritual runner |
| **C compiler** | `ha_silicon_fuse` via `cc` / `build.rs` |
| **Windows** | MSVC Build Tools (not only MinGW) when targeting `*-msvc` |
| **Network (first build)** | crates.io — lockfile is committed as `Cargo.lock` |

Unix CI image: `ubuntu-latest` with Python 3.12 + stable Rust (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## Quick examples

Full write-ups live under [`docs/examples/`](docs/examples/). Below are the same workflows compressed for the front page.

### 1) Full Dual ritual (`lunar_scout`)

**Goal:** Prove Safe allows and Hostile refuses on the teaching lunar scout preset.

```bash
./scripts/bootstrap.sh
# or, bins already built:
ha-production-gate
```

**What happens:** creates a TEMP project → attaches `lunar_scout` → `run_project(safe)` + `run_project(hostile)` → eight falsifiers → stages kit outside the git tree.

**Expect:**

| Check | Intent |
|-------|--------|
| `F_dual_safe_allow_hostile_refuse` | Safe `physics_pass=true`, Hostile `false` |
| `F_hostile_current_refuse` | Hostile `current_allowed=false` |
| `F_named_epsilon_on_seal` | ε list on seal honesty |
| `F_kit_outside_repo_reverify` | Dual JSON re-read from TEMP kit |

Walkthrough: [`docs/examples/01_dual_ritual_lunar_scout.md`](docs/examples/01_dual_ritual_lunar_scout.md)

---

### 2) Read the Dual kit like a reviewer

**Goal:** Open Safe vs Hostile gate fields and explain the refuse to someone else.

```bash
# after a PASS run
ls results/runtime/production_gate_kits/LATEST/
# dual_safe.json  dual_hostile.json  PRODUCTION_GATE.json  README_ENGINEER.md
```

**Typical gate slice (shape):**

```json
{
  "schema": "physics_gate_v1",
  "physics_pass": true,
  "current_allowed": true
}
```

Hostile flips `physics_pass` / `current_allowed` to `false`.  
Guide: [`docs/examples/02_reading_the_kit.md`](docs/examples/02_reading_the_kit.md)

---

### 3) Call the Rust Bekker oracle directly

**Goal:** Evaluate sinkage from the ON-grounded soil catalog without running the full ritual.

```bash
cargo build -p ha_physics_gate --release
./target/release/ha-physics-gate bekker-eval --help
```

Other thermometers on the same bin: `bekker-roundtrip`, `bekker-shear`, `thermal-k`, `dust-ingress`, `mohr-slope`, …  
Guide: [`docs/examples/03_rust_physics_gate_cli.md`](docs/examples/03_rust_physics_gate_cli.md)

---

### 4) Stage a soft release pack

**Goal:** Bundle board + kit for an engineer handoff folder.

```bash
ha-production-gate
ha-release-engineer
ls results/runtime/release_engineer/LATEST/
```

Guide: [`docs/examples/04_soft_release_pack.md`](docs/examples/04_soft_release_pack.md)

---

### 5) Fail closed when the oracle bin is missing

**Goal:** Confirm there is no pure-Python gate fallback.

```bash
# with bins built, ritual PASS
# then rename/move target/release/ha-physics-gate* and re-run — expect hard fail, not a soft PASS
ha-production-gate
```

Guide: [`docs/examples/05_no_python_gate_fallback.md`](docs/examples/05_no_python_gate_fallback.md)

---

## Use cases

### Robotics / autonomy review

- Pre-merge habit: “show me Safe allow + Hostile refuse on this claim”
- Teaching labs: students run Dual before presenting a rover physics story
- Internal dogfood: same ritual CI runs on every push

### Physics / terramech exploration

- Bekker sinkage and shear thermometers via `ha-physics-gate`
- Hostile soils / envelope refuse paths in the Dual stack
- Named honesty ladder before anyone upgrades a label to MEASURED

### Release / evidence hygiene

- Soft pack for an external reader (`ha-release-engineer`)
- Kit outside the repo tree for “receipt left the workshop folder”
- Board markdown you can paste into issues or email

### Companion desk (visual)

- The hero screenshot is the companion Dual desk UI — same Safe/Hostile idea. The **supported install path of this repo remains the CLI**.

---

## Repository map

```text
ha-production-gate/
├── crates/                         # Rust physics & attestation cores
│   ├── ha_physics_gate/            # gate emit/validate + Bekker + thermometers
│   ├── ha_silicon_fuse/            # C/Rust fuse path
│   ├── ha_energy_ledger/
│   ├── ha_body_identity/
│   ├── universe_kinematic/
│   ├── ha_artifact_law/
│   ├── universe_scale/
│   └── ha_iron_attestation/
├── dogfood_platform/               # Python ritual + Dual desk glue (+ portable Clifford oracle)
├── scripts/bootstrap.sh|.ps1       # cold-path build → install → run
├── fixtures/                       # teaching inputs (see fixtures/README.md)
│   ├── open_registry/              # env / terramech catalog JSON
│   ├── open_seed/                  # materials / bind seeds
│   └── robot/                      # lunar_scout recipes + HAL manifests
├── results/platform_bpass/         # frozen teaching bind receipts Dual paths read
├── results/runtime/                # gitignored — boards, kits, desk scratch from local runs
├── docs/examples/                  # detailed walkthroughs (SAS-style)
├── docs/assets/hero-world.png      # README hero (Dual desk)
├── tests/                          # tiny import smoke; CI truth is ha-production-gate
├── START_HERE_PRODUCTION_GATE_V1.md
└── README.md                       # you are here
```

`results/platform_bpass/` stays in-tree on purpose: Dual teaching modules load moon/universe/robot bind receipts from these frozen fixtures. They are teaching receipts, not live CI outputs.

---

## Rust physics gate CLI

```text
ha-physics-gate <COMMAND>
```

Highlights:

| Command | Role |
|---------|------|
| `emit` / `validate` | `physics_gate_v1` JSON |
| `bekker-eval` | Sinkage from soil catalog |
| `bekker-roundtrip` | z↔p identity thermometer |
| `bekker-shear` | Janosi–Hanamoto shear slice |
| `thermal-k` / `radiative-bc` / `dust-ingress` | Regolith / vacuum / dust slices |
| `mohr-slope` / `multipass-rut` / … | Additional teaching thermometers |

Build: `cargo build -p ha_physics_gate --release`

---

## Reading the outputs

| Artifact | Path |
|----------|------|
| Board | `results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md` |
| Ritual JSON | `results/runtime/platform_loop/PRODUCTION_GATE_RITUAL_LATEST_v1.json` |
| Kit mirror | `results/runtime/production_gate_kits/LATEST/` |
| Sample board | [`docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md) |

Falsifiers (honest names):

| id | Meaning |
|----|---------|
| `F_dual_safe_allow_hostile_refuse` | Dual burn |
| `F_kernel_seal_flag_present` | Seal flag on kernel receipt |
| `F_named_epsilon_on_seal` | ε present |
| `F_hostile_current_refuse` | Hostile `current_allowed=false` |
| `F_physics_world_stack_complete` | Hostile physics blocks present |
| `F_soft_mint_detector_alive` | Soft-mint detector responds to probe |
| `F_kit_outside_repo_reverify` | TEMP kit re-read |
| `F_ritual_entrypoint_wired` | Console script + bootstrap + START_HERE |

---

## Soft release pack

```bash
ha-release-engineer
```

Stages `HOW_TO_RUN.md`, board, kit, and manifest under `results/runtime/release_engineer/LATEST/`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `FileNotFoundError` for `ha-physics-gate` | Bins not built | Run bootstrap / five `cargo build --release` lines |
| `ha_silicon_fuse` link errors on Windows | No MSVC | Install VS Build Tools with C++ workload |
| Ritual PASS locally, fail on a clean clone | Author `target/` present | Cold clone + bootstrap on a clean machine |
| Encoding garbage on Windows console | cp1251 | `PYTHONIOENCODING=utf-8` (CI sets this) |
| Long first build | Cold cargo | Expected; `Cargo.lock` keeps the graph pinned |

---

## FAQ

**Is this a ROS package?**  
No. It is a Dual physics ritual + Rust oracle. ROS/Gazebo bridges are future work.

**Does the screenshot mean I get a GUI from this clone?**  
The screenshot is the companion Dual desk. This repo’s supported install path is the CLI (`ha-production-gate`).

**Is a PASS field-MEASURED?**  
No. Soft teaching Dual. See honesty ladder: [`docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md).

**Can Python soft-mint the gate if Rust is missing?**  
No. Missing bin fails closed.

**Do I need another monorepo to run this?**  
No. Clone this repository, bootstrap, and run `ha-production-gate`.

---

## Docs

| Doc | Role |
|-----|------|
| [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md) | 30-second entry |
| [`docs/examples/`](docs/examples/) | Detailed examples index |
| [`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`](docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md) | Ritual canon |
| [`docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md) | Honesty ladder |

---

## Contributing

Fresh-install reports (especially Windows/MSVC), example improvements, and small focused fixes are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

See [`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0 — [`LICENSE`](LICENSE)

**Maintainer:** Stanislav Byriukov — Production Gate
