# Example 07 — Dual socket (body + owned soils)

## Goal

Run Dual on a body a robotics engineer recognizes — `open_diffbot` — or on **your** URDF.
Optionally pass **your** Safe/Hostile soils JSON. Get Safe ALLOW / Hostile REFUSE with sinkage numbers.

This is the **insert point**. The lunar `ha-production-gate` ritual remains CI truth.

## Commands

```bash
./scripts/bootstrap.sh    # once — pip + ensure-bins (or cargo) + Dual socket + CI ritual
ha-ensure-bins
ha-dual-socket --preset open_diffbot
```

Owned soils (your Safe/Hostile + contact on the board):

```bash
ha-dual-socket --preset open_diffbot \
  --soils fixtures/open_registry/terramech/dual_owned_soils_example_v1.json

# edit-me embedded params:
ha-dual-socket --preset open_diffbot \
  --soils fixtures/open_registry/terramech/dual_owned_soils_embedded_v1.json
```

Docker:

```bash
docker compose run --rm dual
```

Your URDF:

```bash
ha-dual-socket --urdf path/to/robot.urdf --kind wheeled_base \
  --soils path/to/my_soils.json
# optional contact overrides (also allowed inside soils JSON):
#   --mass-kg 48 --n-contacts 4 --contact-width-m 0.055 --contact-length-m 0.09
```

Desk:

```bash
ha-desk
# http://127.0.0.1:8765 — pick preset or upload URDF → Run Dual
```

## Owned soils schema (`ha_dual_owned_soils_v1`)

```json
{
  "schema": "ha_dual_owned_soils_v1",
  "g_mps2": 9.81,
  "safe": "my_firm",
  "hostile": "my_soft",
  "soils": {
    "my_firm": { "n": 1.0, "kc": 40.0, "k_phi": 2000.0 },
    "my_soft": { "n": 0.8, "kc": 5.0, "k_phi": 80.0 }
  },
  "contact": {
    "mass_kg": 48.0,
    "n_contacts": 4.0,
    "contact_width_m": 0.055,
    "contact_length_m": 0.09
  }
}
```

- `safe` / `hostile` may also reference ids in the default Bekker catalog (`firm_lab`, `soft_hostile`, Wong rows, …).
- Board prints **contact used** and soil ids — nothing hidden.

## CI bit

Copy [`.github/workflows/dual-socket.yml`](../../.github/workflows/dual-socket.yml) into your repo (or point `--urdf` / `--soils` at your paths). Exit code ≠ 0 unless Hostile refuses.

## Expect

```text
verdict: DUAL_SOCKET_PASS
contact: mass_kg=… n=… w=… L=…
soils:   safe=… hostile=… owned=True
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
Soils examples: `fixtures/open_registry/terramech/dual_owned_soils_*.json`

## Honesty

Soft teaching Dual · teaching contact unless you pass owned contact · not MEASURED CAD · not a Gazebo plugin · not a ROS package yet.

Next: [08 Stranger URDF + owned soils](08_stranger_urdf_owned_soils.md) · [01 ritual](01_dual_ritual_lunar_scout.md) · [06 Sinkage bench](06_sinkage_dual_bench.md)
