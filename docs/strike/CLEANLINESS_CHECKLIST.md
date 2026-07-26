# Cleanliness checklist — strike pack

Run before any send. Fail any row ⇒ do not post.

## Forbidden in strike text / linked public face

| Pattern | Status |
|---------|--------|
| Odysseus / other-product “inspired by” | must be absent |
| `hardware_atom` / private workshop paths | must be absent |
| `C:\Users\…` / `/Users/…` absolute home paths | must be absent |
| hire-claim / visa / NIW / immigration ask | must be absent |
| “NASA certified” / “SPX certified” | must be absent |
| “What this is not” disclaimer-table as the hook | must be absent |
| SHOW_HN_DRAFT / SURFACE_MANIFEST operator dumps | must be absent |
| Soft-mint MEASURED / OTP as product claim | must be absent |

## Required in strike text

| Item | Status |
|------|--------|
| Public URL `ha-production-gate` | required |
| Dual Safe ALLOW / Hostile REFUSE | required |
| Rust oracle / fail-closed | required |
| Soft teaching · not MEASURED | required |
| Cold path `bootstrap` or equivalent | required |
| Link to tech note | required |
| CLI = install path (desk = companion visual only) | required |

## Pre-send commands (operator machine)

```bash
cd ha-production-gate
git grep -i -E "odysseus|hardware_atom|hire-claim|\\\\Users\\\\|SHOW_HN_DRAFT|certified" docs/strike README.md START_HERE_PRODUCTION_GATE_V1.md NOTICE
# expect: no hits

./scripts/bootstrap.sh   # or rely on green CI on main
# expect: PRODUCTION_GATE_RITUAL_PASS
```

## Pack files

- `docs/strike/README.md`
- `docs/strike/01_ROS_SIM_POST.md`
- `docs/strike/03_SHOW_HN.md`
- `docs/strike/TECH_NOTE_DUAL_REFUSE_V0.md`
