<p align="center">
  <strong>HA Production Gate</strong>
</p>

<p align="center">
  A Dual physics check for robot and autonomy claims: Safe must allow, Hostile must refuse — with a sealed receipt and a Rust physics oracle.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="START_HERE_PRODUCTION_GATE_V1.md">Start here</a> ·
  <a href="docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md">Ritual</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/StanByriukov02/ha-production-gate/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/StanByriukov02/ha-production-gate/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="https://github.com/StanByriukov02/ha-production-gate/releases"><img src="https://img.shields.io/github/v/release/StanByriukov02/ha-production-gate?include_prereleases&sort=semver&label=version" alt="version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/StanByriukov02/ha-production-gate" alt="license"></a>
</p>

<p align="center">
  <img src="docs/assets/hero-world.png" alt="Hardware Atom Dual desk — Safe / Hostile sinkage">
</p>

---

## Quick Start

Needs Rust, Python ≥ 3.11, and a C compiler for `ha_silicon_fuse` (Windows: MSVC Build Tools). First cold build can take a few minutes.

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

When it finishes you should see `PRODUCTION_GATE_RITUAL_PASS` and a board under `results/runtime/platform_loop/`.

Manual steps (same as bootstrap): build the five Rust release bins, `pip install -e .`, then `ha-production-gate`. Details in [`START_HERE_PRODUCTION_GATE_V1.md`](START_HERE_PRODUCTION_GATE_V1.md).

---

## Features

- **Dual world** — same stack run in Safe and Hostile; Hostile must refuse or the ritual fails.
- **Rust physics gate** — Bekker / gate decision in `ha-physics-gate`; Python only orchestrates.
- **Sealed receipt** — board + JSON with named honesty (`ε`) you can keep and re-read.
- **Stranger kit** — Dual receipts staged outside the git tree on your machine after the run.
- **One command path** — `./scripts/bootstrap.sh` (or `ha-production-gate` once bins are built).
- **CI-proven on Unix** — GitHub Actions builds the bins and runs the same ritual on every push to `main`.

Soft release today: teaching Dual on the public surface. Field MEASURED / HIL / OTP are later rungs on the honesty ladder — see [`PHYSICS_OS_KERNEL_V0.md`](docs/agent_workflow/PHYSICS_OS_KERNEL_V0.md).

---

## What you get

A pass/fail engineer board, a JSON receipt, and Dual Safe/Hostile artifacts you can show another engineer.

```text
════════════════════════════════════════════════════════════
  HA PRODUCTION GATE
  verdict: PRODUCTION_GATE_RITUAL_PASS

  [PASS] F_dual_safe_allow_hostile_refuse
  [PASS] F_hostile_current_refuse
  [PASS] F_named_epsilon_on_seal
  …
════════════════════════════════════════════════════════════
```

Sample: [`docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md`](docs/examples/PRODUCTION_GATE_BOARD_SAMPLE.md)

The hero image above is the companion Dual desk from Hardware Atom — the same Safe/Hostile idea in UI form. This repository’s install path is the CLI ritual.

---

## Soft release pack

```bash
ha-release-engineer
# stages results/runtime/release_engineer/LATEST/
```

---

## Contributing

Fresh-install testing, Windows/MSVC friction reports, docs, and small focused fixes are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

See [`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0 — [`LICENSE`](LICENSE)

**Maintainer:** Stanislav Byriukov
