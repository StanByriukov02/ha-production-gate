# Fixtures

Teaching and open-seed inputs for the Dual ritual. Nothing here is field-MEASURED.

| Path | Role |
|------|------|
| `open_registry/` | ON-grounded env / terramech catalog JSON used by Python glue thermometers |
| `open_registry/field/` | Globe → Dual soils + g bind (Moon 1.62 / Earth 9.81 / …) |
| `open_seed/` | Materials / bind seeds resolved before moon `platform_bpass` fallbacks |
| `robot/` | Assembly recipes and HAL/manifest slices for presets such as `lunar_scout` |
| `cad/scout/` | Minimal scout fact JSON still referenced by torso/head mechanical slices |

URDF meshes for the ritual live under `dogfood_platform/robot_models/urdf/` (not a CAD dump tree).

Runtime desk scratch (active project pointer, start-here session) writes under `results/runtime/` (gitignored), not under this folder.
