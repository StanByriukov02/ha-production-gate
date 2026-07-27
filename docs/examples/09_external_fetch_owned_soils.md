# Example 09 — Third-party URDF (Fetch Robotics) + owned soils

## Goal

Dual on a body **HA did not author**: Fetch mobile manipulator URDF from upstream `fetch_ros`, plus owned Safe/Hostile soil ids.

This is stronger stranger-proof than Example 08 (our open-registry skid-steer).

## Claim class

Soft teaching Dual · Bekker ON · **not** MEASURED · **not** OEM endorsement · meshes not shipped (`package://` ignored for kinematics).

## Upstream

- Source: [fetchrobotics/fetch_ros](https://github.com/fetchrobotics/fetch_ros) · `fetch_description/robots/fetch.urdf` (melodic-devel snapshot)
- Local copy: [`fixtures/open_registry/urdf/_external/fetch.urdf`](../../fixtures/open_registry/urdf/_external/fetch.urdf)
- Attribution: [`fixtures/open_registry/urdf/_external/README.md`](../../fixtures/open_registry/urdf/_external/README.md)

## Frozen receipt

[`external_fetch_owned_soils_v1.json`](external_fetch_owned_soils_v1.json)

## Reproduce

```bash
ha-ensure-bins
ha-dual-socket \
  --urdf fixtures/open_registry/urdf/_external/fetch.urdf \
  --root-link base_link \
  --ee-link gripper_link \
  --kind wheeled_base \
  --soils fixtures/open_registry/terramech/dual_owned_soils_fetch_v1.json
```

## Table (captured Dual)

| Lane | Soil id | `sinkage_mm` | Gate |
|------|---------|--------------|------|
| **Safe** | `fetch_firm_owned` | **8.805** | ALLOW |
| **Hostile** | `fetch_soft_owned` | **117.009** | REFUSE |

Contact used (teaching override — not Fetch CAD MEASURED): `mass_kg=95` · `n=2` · `0.12×0.18` m · verdict `DUAL_SOCKET_PASS`.

## Honesty

First attempt with a tiny pad failed Safe too (honest FAIL). Contact was widened to a teaching wheel patch so Dual separates — still **not** a field load cell.

Prev: [08 Stranger skid](08_stranger_urdf_owned_soils.md) · [07 Socket](07_dual_socket.md)
