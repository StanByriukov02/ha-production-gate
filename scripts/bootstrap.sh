#!/usr/bin/env bash
# Cold path: build Rust bins → venv → install → Dual socket (robotics wow) → CI ritual.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }; }
need cargo
need python3

echo "==> cargo release bins (physics oracle — not pip-only yet)"
cargo build -p ha_physics_gate --release
cargo build -p ha_silicon_fuse --release
cargo build -p ha_energy_ledger --release
cargo build -p ha_body_identity --release
cargo build -p universe_kinematic --release --bin manipulator_kinematics_step

echo "==> python venv + install"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e .

echo "==> Dual socket (primary wow — open_diffbot)"
ha-dual-socket --preset open_diffbot

echo "==> CI ritual (lunar_scout falsifiers)"
ha-production-gate

echo ""
echo "OK — next: ha-desk   # local Dual UI on http://127.0.0.1:8765"
echo "     or:  ha-dual-socket --urdf path/to/your.urdf --kind wheeled_base"
