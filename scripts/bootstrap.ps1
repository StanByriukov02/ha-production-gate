# Cold path (Windows): build Rust physics bins → venv → install → run gate ritual.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Need([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "missing: $Name"
  }
}

Need cargo
Need python

Write-Host "==> cargo release bins"
cargo build -p ha_physics_gate --release
cargo build -p ha_silicon_fuse --release
cargo build -p ha_energy_ledger --release
cargo build -p ha_body_identity --release
cargo build -p universe_kinematic --release --bin manipulator_kinematics_step

Write-Host "==> python venv + install"
if (-not (Test-Path .venv)) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -e .

Write-Host "==> ha-production-gate"
& .\.venv\Scripts\ha-production-gate.exe
