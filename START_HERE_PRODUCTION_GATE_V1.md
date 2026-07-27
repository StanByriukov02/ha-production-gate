# Start here

**Fail mobility claims that only look green on firm soil.**

```bash
./scripts/bootstrap.sh          # Windows: .\scripts\bootstrap.ps1
# primary wow: ha-dual-socket --preset open_diffbot → DUAL_SOCKET_PASS
# then CI ritual: ha-production-gate
```

Docker (after first image build):

```bash
docker compose run --rm dual
```

Local desk:

```bash
ha-desk
# http://127.0.0.1:8765
```

| Next | Open |
|------|------|
| Full face | [`README.md`](README.md) |
| Socket walkthrough | [`docs/examples/07_dual_socket.md`](docs/examples/07_dual_socket.md) |
| Dual method | [`docs/DUAL_REFUSE.md`](docs/DUAL_REFUSE.md) |
