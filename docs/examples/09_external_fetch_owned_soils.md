# Example 09 — Third-party Fetch URDF: Gate told the truth (FAIL)

## Product point

People do **not** come here for a green `DUAL_SOCKET_PASS`.

They come for a **hard physics check before hardware** — Safe must allow and Hostile must refuse *when the claim is real*. If Safe also sinks, the Gate **fails the claim**. That is the factory working.

This example freezes that lesson on a **third-party** body (Fetch Robotics), with contact **not** widened to buy a demo PASS.

## Upstream

- [fetchrobotics/fetch_ros](https://github.com/fetchrobotics/fetch_ros) · `fetch.urdf`
- Local: [`fixtures/open_registry/urdf/_external/fetch.urdf`](../../fixtures/open_registry/urdf/_external/fetch.urdf)

## Reproduce

```bash
ha-dual-socket \
  --urdf fixtures/open_registry/urdf/_external/fetch.urdf \
  --root-link base_link \
  --ee-link gripper_link \
  --kind wheeled_base \
  --soils fixtures/open_registry/terramech/dual_owned_soils_fetch_v1.json
# expect exit code 1 · verdict DUAL_SOCKET_FAIL
```

## Captured result

| Lane | Soil id | `sinkage_mm` | Gate |
|------|---------|--------------|------|
| Safe | `fetch_firm_owned` | **36.982** | REFUSE |
| Hostile | `fetch_soft_owned` | **700.643** | REFUSE |

**Verdict:** `DUAL_SOCKET_FAIL` — Dual did not separate (Safe did not allow).  
Declared contact: `mass_kg=95` · `n=2` · `0.10×0.05` m (teaching patch, not MEASURED CAD).

Frozen: [`external_fetch_owned_soils_v1.json`](external_fetch_owned_soils_v1.json)

## How to read it

| Wrong reading | Right reading |
|---------------|---------------|
| «Demo broken» | Claim does not clear the Gate under declared load/patch |
| «Widen contact until PASS» | Change **physics inputs** only if they are more true — never to paint green |
| «PASS = success» | **Truth before hardware** = success |

Example 08 remains a clean Dual-separating worked example. Example 09 is the refuse factory.

Prev: [08](08_stranger_urdf_owned_soils.md) · [07](07_dual_socket.md)
