# Contributing

Thanks for caring about Production Gate.

## What helps most

1. Run `ha-production-gate` on a clean machine and open an issue with your board (PASS or FAIL).
2. Fix cold-path friction (docs, missing crate in Quick Start, Windows encoding).
3. Keep honesty locks: no soft-mint MEASURED / OTP; physics oracle stays Rust.

## Dev loop

```bash
pip install -e .
# build the five release bins (see README Quick Start)
ha-production-gate
```

Optional import smoke:

```bash
pip install -e ".[smoke]"
pytest
```

## PR rules

- One concern per PR.
- Do not add private workshop paths, journals, or personal packets to this public tree.
- Do not expand scope into private workshop trees outside this clone.
- CI must stay green (`ha-production-gate` PASS).

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
