# Contributing

Thanks for caring about Production Gate.

## What helps most

1. Run `ha-production-gate` on a clean machine and open an issue with your board (PASS or FAIL).
2. Fix cold-path friction (docs, missing crate in Quick Start, Windows encoding).
3. Keep honesty locks: no soft-mint MEASURED / OTP; physics oracle stays Rust.

## Dev loop

```bash
pip install -e ".[smoke]"
# build the five release bins (see README Quick Start)
ha-production-gate
```

## PR rules

- One concern per PR.
- Do not add vault paths, operator journals, or NIW packets.
- Do not expand scope into the full private Hardware Atom workshop.
- CI must stay green (`ha-production-gate` PASS).

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
