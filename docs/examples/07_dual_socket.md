# Example 07 — Dual socket (ROS body or your URDF)

## Goal

Run Dual on a body a robotics engineer recognizes — `open_diffbot` — or on **your** URDF. Get Safe ALLOW / Hostile REFUSE with sinkage numbers.

This is the **insert point**. The lunar `ha-production-gate` ritual remains CI truth.

## Commands

```bash
./scripts/bootstrap.sh    # once — builds Rust + Dual socket + CI ritual
ha-dual-socket --preset open_diffbot
```

Docker:

```bash
docker compose run --rm dual
```

Your URDF:

```bash
ha-dual-socket --urdf path/to/robot.urdf --kind wheeled_base
# optional contact overrides:
#   --mass-kg 48 --n-contacts 4 --contact-width-m 0.055 --contact-length-m 0.09
```

Desk:

```bash
ha-desk
# http://127.0.0.1:8765 — pick preset or upload URDF → Run Dual
```

## Expect

```text
verdict: DUAL_SOCKET_PASS
Safe     … sinkage_mm=…  pass=True allowed=True
Hostile  … sinkage_mm=…  pass=False allowed=False
```

Board: `results/runtime/platform_loop/DUAL_SOCKET_BOARD_LATEST.md`

## Open bodies in this repo

| Preset / registry | Role |
|-------------------|------|
| `open_diffbot` | ROS tutorial-class differential base |
| `open_rrbot` | ROS / Gazebo-style 2-DoF arm |
| `lunar_scout` | Teaching hexapod (also CI ritual) |
| `earth_bench` | Earth bench recipe |

URDFs: `fixtures/open_registry/urdf/` · registry: `fixtures/open_registry/REGISTRY_v1.json`

## Honesty

Soft teaching Dual · teaching contact geometry · not MEASURED CAD · not a Gazebo plugin · not a ROS package yet.

Next: [01_dual_ritual_lunar_scout.md](01_dual_ritual_lunar_scout.md) · [06_sinkage_dual_bench.md](06_sinkage_dual_bench.md)
