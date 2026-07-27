# Cold path (Windows): prefer prebuilt bins → Dual socket → CI ritual.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Need([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "missing: $Name"
  }
}

Need python

Write-Host "==> python venv + install"
if (-not (Test-Path .venv)) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -e .

Write-Host "==> Dual oracle bins (prebuilt preferred)"
& .\.venv\Scripts\ha-ensure-bins.exe
if ($LASTEXITCODE -ne 0) {
  Write-Host "prebuilt miss — falling back to cargo"
  Need cargo
  cargo build -p ha_physics_gate --release
  cargo build -p ha_silicon_fuse --release
  cargo build -p ha_energy_ledger --release
  cargo build -p ha_body_identity --release
  cargo build -p universe_kinematic --release --bin manipulator_kinematics_step
}

Write-Host "==> Dual socket (primary wow — open_diffbot)"
& .\.venv\Scripts\ha-dual-socket.exe --preset open_diffbot
if ($LASTEXITCODE -ne 0) { throw "ha-dual-socket failed" }

Write-Host "==> CI ritual (lunar_scout falsifiers)"
& .\.venv\Scripts\ha-production-gate.exe
if ($LASTEXITCODE -ne 0) { throw "ha-production-gate failed" }

Write-Host ""
Write-Host "OK — next: ha-desk   # local Dual UI on http://127.0.0.1:8765"
Write-Host "     or:  ha-dual-socket --urdf path\to\your.urdf --kind wheeled_base"
