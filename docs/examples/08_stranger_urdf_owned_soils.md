# Example 08 — Stranger URDF + owned soils (exit GitHub-as-endpoint)

## Goal

Prove the wedge is **not** “our teaching world again”:

- **Body:** open `ros_skidsteer` URDF (not `open_diffbot` preset, not `lunar_scout`)
- **Soils:** owned ids `skid_firm_owned` / `skid_soft_owned` (not `firm_lab` / `soft_hostile`)
- **Contact:** explicit on the board (mass / pads)

This is the public artifact for the next graph ask and Dust FG one-liner — Example 06 stays history; **07/08 are the insert story**.

## Claim class

Soft teaching Dual · Bekker ON · **not** field MEASURED · **not** HIL · **not** a Gazebo/ROS plugin.

## Frozen receipt

[`stranger_urdf_owned_soils_skidsteer_v1.json`](stranger_urdf_owned_soils_skidsteer_v1.json)

## Reproduce

```bash
pip install -e .
ha-ensure-bins   # or cargo build -p ha_physics_gate --release
ha-dual-socket \
  --urdf fixtures/open_registry/urdf/ros_skidsteer_v1.urdf \
  --kind wheeled_base \
  --soils fixtures/open_registry/terramech/dual_owned_soils_skidsteer_v1.json
```

Soils pack: [`fixtures/open_registry/terramech/dual_owned_soils_skidsteer_v1.json`](../../fixtures/open_registry/terramech/dual_owned_soils_skidsteer_v1.json)

## Table (captured Dual)

| Lane | Soil id | `sinkage_mm` | Gate |
|------|---------|--------------|------|
| **Safe** | `skid_firm_owned` | **9.546** | `physics_pass=true` · `current_allowed=true` |
| **Hostile** | `skid_soft_owned` | **69.118** | `physics_pass=false` · `current_allowed=false` |

Shared bind (owned contact):

| Field | Value |
|-------|-------|
| Body | `fixtures/open_registry/urdf/ros_skidsteer_v1.urdf` |
| `g` | `9.81` m/s² |
| `mass_kg` | `62` |
| `n_contacts` | `4` |
| pad | `0.07 × 0.12` m |
| Verdict | `DUAL_SOCKET_PASS` |

Your numbers will match **shape** (Safe allow · Hostile refuse · owned ids). Exact mm may move if you edit the soils JSON — that is the point.

## CI bit

Copy [`.github/workflows/dual-socket.yml`](../../.github/workflows/dual-socket.yml) and point `--urdf` / `--soils` at *your* paths.

## Ask shape (for humans — not agent SEND)

```text
Same skid-steer open URDF, two owned soils (not our teaching defaults).
Safe ~9.5 mm ALLOW · Hostile ~69 mm REFUSE. Soft teaching Dual.

Reproduce:
https://github.com/StanByriukov02/ha-production-gate/blob/main/docs/examples/08_stranger_urdf_owned_soils.md

Ask: does Safe/Hostile with *your* soil params help avoid traverse claims
that only looked green on firm ground?
```

## Honesty

- Soil ids are owned labels — not Wong table rows unless you put Wong numbers in
- Contact is teaching-explicit, not CAD inertia
- Not MEASURED · not product_ready · not NASA certified

Prev: [07 Dual socket](07_dual_socket.md) · [06 Sinkage bench](06_sinkage_dual_bench.md)
