# Fixtures

Teaching and open-seed inputs for Dual. Nothing here is field-MEASURED.

| Path | Role |
|------|------|
| `open_registry/REGISTRY_v1.json` | Open ROS tutorial bodies (diffbot, rrbot, …) |
| `open_registry/urdf/` | Those URDFs — socket / desk entry |
| `open_registry/` env · terramech | ON-grounded catalogs for Python glue thermometers |
| `open_registry/field/` | Globe → Dual soils + g bind |
| `open_seed/` | Materials / bind seeds |
| `robot/` | Assembly recipes / HAL for presets such as `lunar_scout` |
| `cad/scout/` | Minimal scout fact JSON for mechanical slices |

Assembly URDFs also live under `dogfood_platform/robot_models/urdf/`.

Runtime scratch (BYO URDF, boards, kits) → `results/runtime/` (gitignored).
