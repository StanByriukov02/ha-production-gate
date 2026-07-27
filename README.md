# HA Production Gate

[![CI](https://img.shields.io/github/actions/workflow/status/StanByriukov02/ha-production-gate/ci.yml?branch=main&label=CI)](https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/release/StanByriukov02/ha-production-gate?include_prereleases&sort=semver&label=version)](https://github.com/StanByriukov02/ha-production-gate/releases)
[![License](https://img.shields.io/github/license/StanByriukov02/ha-production-gate)](LICENSE)
[![Rust](https://img.shields.io/badge/physics_oracle-Rust-b45309)](crates/ha_physics_gate)
[![Python](https://img.shields.io/badge/Python_3.11%2B-3776AB)](production_gate)

**Production Gate**

Fail mobility claims that only look green on **firm soil**.

Same URDF body · two soils · **Safe must allow · Hostile must refuse** · Rust Bekker oracle · board you can paste.

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ha-ensure-bins                 # download Dual bins (no Cargo) — or cargo fallback via bootstrap
ha-dual-socket --preset open_diffbot
ha-desk                        # http://127.0.0.1:8765
```

One-shot scripts (prebuilt bins preferred, Cargo only if download misses):

```bash
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
docker compose run --rm dual    # after image build
```

Not a Gazebo plugin. Not a ROS package. A **referee** on open_diffbot or your URDF.

<p align="center">
  <img src="docs/assets/hero-dual-socket.svg" alt="Dual socket — Safe 8.72 mm allow · Hostile 84.99 mm refuse" width="960">
</p>

**Taste (what `ha-dual-socket` should print):**

```text
verdict: DUAL_SOCKET_PASS
Safe     soil=firm_lab       sinkage_mm=8.72   pass=True  allowed=True
Hostile  soil=soft_hostile   sinkage_mm=84.99  pass=False allowed=False
```

---

## What's included

| Layer | What you get |
|-------|----------------|
| **Dual socket** | `ha-dual-socket` — `--preset open_diffbot` or `--urdf your.urdf` → sinkage board |
| **Ensure bins** | `ha-ensure-bins` — download Dual oracle bins from `bins-latest` (skip Cargo) |
| **Dual desk** | `ha-desk` — local UI (`desk/index.html`) · pick body · Run Dual |
| **CI ritual** | `ha-production-gate` — full falsifier ritual (`lunar_scout` teaching) |
| **Bootstrap** | `scripts/bootstrap.sh` / `.ps1` — pip → ensure-bins (or cargo) → socket → ritual |
| **Docker** | `docker compose run --rm dual` |
| **Rust oracle** | `ha-physics-gate` Bekker + thermometers (prebuilt or cargo) |
| **Open bodies** | `fixtures/open_registry/urdf/` — diffbot / rrbot / skidsteer / arm4 |
| **Examples** | [`docs/examples/`](docs/examples/) — ritual, kit, **socket**, sinkage bench |

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

### You get a number, not a sermon

Safe vs Hostile **sinkage_mm** + gate bits on a body you chose. Paste the board into a review. Soft teaching — not field MEASURED.

### Catch “always green” mobility stories

A traverse claim that only ever ran on firm soil can look healthy forever. Hostile must refuse.

### Speak robotics entry, not only lunar ritual

`open_diffbot` is a ROS tutorial-class base. Or `--urdf your.urdf`. CI still uses `ha-production-gate` (`lunar_scout`) as the full falsifier ritual.

### Honest scope (read this)

| This is | This is not |
|---------|-------------|
| Dual Bekker referee + local desk | Gazebo / Chrono soil plugin |
| URDF → board | Nav2 node / `ros2 launch` stack |
| `ha-ensure-bins` prebuilts (linux/windows x86_64) | Universal pip wheel with embedded Rust (not yet) |
| Teaching contact geometry | MEASURED CAD inertia / flight soil ID |
| Rust oracle, fail-closed | Pure-Python soft PASS |

---

## Quick start

**Pip-first (no Cargo when `bins-latest` is published):**

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ha-ensure-bins
ha-dual-socket --preset open_diffbot
```

**Bootstrap** (same: prebuilt preferred, Cargo fallback, then socket + ritual):

```bash
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

**Docker** (after image build):

```bash
docker compose run --rm dual
```

**Desk:**

```bash
ha-desk
# http://127.0.0.1:8765
```

If `ha-ensure-bins` says download failed: install [Rust](https://rustup.rs/) and re-run bootstrap (builds five Dual bins once).

Short entry: [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md) · method: [`docs/DUAL_REFUSE.md`](docs/DUAL_REFUSE.md) · socket: [`docs/examples/07_dual_socket.md`](docs/examples/07_dual_socket.md)

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
ha-dual-socket --preset open_diffbot
ha-production-gate   # CI ritual
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

### 1) Dual socket — ROS-shaped body or your URDF

**Goal:** Insert point for robotics — not only the lunar teaching ritual.

```bash
ha-dual-socket --preset open_diffbot
# or
ha-dual-socket --urdf path/to/your_robot.urdf --kind wheeled_base
ha-desk
```

Expect `DUAL_SOCKET_PASS` and Safe vs Hostile `sinkage_mm` on the board.  
Walkthrough: [`docs/examples/07_dual_socket.md`](docs/examples/07_dual_socket.md)

---

### 2) Full Dual ritual (`lunar_scout`) — CI truth

**Goal:** Prove Safe allows and Hostile refuses on the teaching lunar scout preset (CI / bootstrap).

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

**Sinkage Dual tip:** Safe `lunar_firm_proxy` ≈ **5.2 mm** ALLOW · Hostile `lunar_soft_proxy` ≈ **136 mm** REFUSE (cap 18 mm) — [`docs/examples/06_sinkage_dual_bench.md`](docs/examples/06_sinkage_dual_bench.md).

---

### 3) Read the Dual kit like a reviewer

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

### 4) Call the Rust Bekker oracle directly

**Goal:** Evaluate sinkage from the ON-grounded soil catalog without running the full ritual.

```bash
cargo build -p ha_physics_gate --release
./target/release/ha-physics-gate bekker-eval --help
```

Other thermometers on the same bin: `bekker-roundtrip`, `bekker-shear`, `thermal-k`, `dust-ingress`, `mohr-slope`, …  
Guide: [`docs/examples/03_rust_physics_gate_cli.md`](docs/examples/03_rust_physics_gate_cli.md)

---

### 5) Stage a soft release pack

**Goal:** Bundle board + kit for an engineer handoff folder.

```bash
ha-production-gate
ha-release-engineer
ls results/runtime/release_engineer/LATEST/
```

Guide: [`docs/examples/04_soft_release_pack.md`](docs/examples/04_soft_release_pack.md)

---

### 6) Fail closed when the oracle bin is missing

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
- Internal gate: same ritual CI runs on every push

### Physics / terramech exploration

- Bekker sinkage and shear thermometers via `ha-physics-gate`
- Hostile soils / envelope refuse paths in the Dual stack
- Named honesty ladder before anyone upgrades a label to MEASURED

### Release / evidence hygiene

- Soft pack for an external reader (`ha-release-engineer`)
- Kit outside the repo tree for “receipt left the workshop folder”
- Board markdown you can paste into issues or email

### Dual desk (local app)

```bash
ha-desk
```

Serves [`desk/index.html`](desk/index.html) on `127.0.0.1:8765`. Pick `open_diffbot` or upload a URDF → Run Dual. Local only.

The README hero is a Dual scene still; the **supported desk path is `ha-desk`**.

---

## Repository map

```text
ha-production-gate/
├── crates/                         # Rust physics & attestation cores
│   ├── ha_physics_gate/            # gate emit/validate + Bekker + thermometers
│   ├── ha_silicon_fuse/
│   ├── ha_energy_ledger/
│   ├── ha_body_identity/
│   ├── universe_kinematic/
│   ├── ha_artifact_law/
│   ├── universe_scale/
│   └── ha_iron_attestation/
├── production_gate/               # Python socket · desk server · ritual glue
├── desk/index.html                 # Dual desk UI (served by ha-desk)
├── Dockerfile · docker-compose.yml # one-command Dual socket image
├── scripts/bootstrap.sh|.ps1       # cold-path → socket wow → ritual
├── fixtures/                       # teaching inputs (see fixtures/README.md)
│   ├── open_registry/              # env / terramech + REGISTRY + urdf/
│   ├── open_seed/
│   └── robot/
├── results/platform_bpass/         # frozen teaching bind receipts
├── results/runtime/                # gitignored — boards, kits, BYO URDF scratch
├── docs/examples/
├── docs/assets/hero-world.png
├── tests/
├── START_HERE_PRODUCTION_GATE_V1.md
└── README.md
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
Not yet. Socket today: open tutorial URDF / your URDF → Dual board. ROS/Gazebo plugin bridges are future work.

**Is there a GUI?**  
Yes — local only: `ha-desk` → `http://127.0.0.1:8765`. CLI twin: `ha-dual-socket`.

**Is a PASS field-MEASURED?**  
No. Soft teaching Dual. See honesty ladder: [`docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md).

**Can Python soft-mint the gate if Rust is missing?**  
No. Missing bin fails closed.

**Do I need another monorepo to run this?**  
No. Clone this repository, bootstrap, then `ha-dual-socket` / `ha-desk` / `ha-production-gate`.

---

## Docs

| Doc | Role |
|-----|------|
| [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md) | 30-second entry |
| [`docs/examples/`](docs/examples/) | Detailed examples index |
| [`docs/DUAL_REFUSE.md`](docs/DUAL_REFUSE.md) | Dual Safe/Hostile refuse method + honesty |
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
