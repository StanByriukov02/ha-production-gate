#!/usr/bin/env bash
# Cold path: prefer prebuilt bins (no Cargo) → Dual socket → CI ritual.
# Falls back to cargo build if ha-ensure-bins cannot download bins-latest.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
need python3

echo "==> python venv + install"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e .

echo "==> Dual oracle bins (prebuilt preferred)"
if ha-ensure-bins; then
  echo "using prebuilt / existing bins under target/release"
else
  echo "prebuilt miss — falling back to cargo"
  need cargo
  cargo build -p ha_physics_gate --release
  cargo build -p ha_silicon_fuse --release
  cargo build -p ha_energy_ledger --release
  cargo build -p ha_body_identity --release
  cargo build -p universe_kinematic --release --bin manipulator_kinematics_step
fi

echo "==> Dual socket (primary wow — open_diffbot)"
ha-dual-socket --preset open_diffbot

echo "==> CI ritual (lunar_scout falsifiers)"
ha-production-gate

echo ""
echo "OK — next: ha-desk   # local Dual UI on http://127.0.0.1:8765"
echo "     or:  ha-dual-socket --urdf path/to/your.urdf --kind wheeled_base"
