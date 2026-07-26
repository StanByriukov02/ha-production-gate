# Start here

HA Production Gate is a Dual physics check: Safe must allow, Hostile must refuse. Rust owns the gate; Python runs the ritual.

```bash
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Expect `PRODUCTION_GATE_RITUAL_PASS` and a board at `results/runtime/platform_loop/PRODUCTION_GATE_BOARD_LATEST.md`.

| You should see | Meaning |
|----------------|---------|
| Safe `physics_pass=true` | Safe world allows |
| Hostile `physics_pass=false` | Hostile world refuses |
| Named `epsilon` on the receipt | Honesty labels stay attached |

Full face: [`README.md`](README.md) · canon: [`docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md`](docs/agent_workflow/PRODUCTION_GATE_RITUAL_V1.md)
