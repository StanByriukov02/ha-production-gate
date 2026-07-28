# Start here

**Fail mobility claims that only look green on firm soil.**

```bash
git clone https://github.com/StanByriukov02/ha-production-gate.git
cd ha-production-gate
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
ha-ensure-bins                                      # Dual bins without Cargo when published
ha-dual-socket --preset open_diffbot
```

Or one script (prebuilt → cargo fallback → socket → ritual):

```bash
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
```

Docker: `docker compose run --rm dual` · Desk: `ha-desk`

| Next | Open |
|------|------|
| Full face | [`README.md`](README.md) |
| Socket | [`docs/examples/07_dual_socket.md`](docs/examples/07_dual_socket.md) |
| Thin ros2 (T5) | [`docs/examples/10_thin_ros2_dual.md`](docs/examples/10_thin_ros2_dual.md) |
| Dual method | [`docs/DUAL_REFUSE.md`](docs/DUAL_REFUSE.md) |
