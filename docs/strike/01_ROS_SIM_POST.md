# Channel 1 — ROS / sim communities

**Paste-ready.** Trim the opener to match the room (Discourse vs Discord).  
**Link always:** https://github.com/StanByriukov02/ha-production-gate  
**Method:** https://github.com/StanByriukov02/ha-production-gate/blob/main/docs/strike/TECH_NOTE_DUAL_REFUSE_V0.md

---

## Short (Discord / Slack)

Built a small **Dual physics gate** you can clone and run:

Same body/stack twice → **Safe must ALLOW**, **Hostile must REFUSE**. Gate boolean comes from **Rust** (`ha-physics-gate`), not a Python soft-PASS. You get a board + Dual JSON receipts.

Repo: https://github.com/StanByriukov02/ha-production-gate  
`./scripts/bootstrap.sh` → expect `PRODUCTION_GATE_RITUAL_PASS`

Soft teaching Dual (not field MEASURED / not HIL). Looking for people who ship Nav2/MoveIt/Gazebo stacks and care whether Hostile can still say no.

Method note: https://github.com/StanByriukov02/ha-production-gate/blob/main/docs/strike/TECH_NOTE_DUAL_REFUSE_V0.md

---

## Longer (ROS Discourse / forum)

**Title:** Dual Safe/Hostile physics gate (Rust oracle) — cloneable refuse ritual before you trust a green claim

Most autonomy stacks can stay green forever if you only ever run the friendly world.

I open-sourced a **Production Gate** CLI that runs the same teaching stack twice:

- **Safe** → physics gate must **ALLOW**
- **Hostile** → same gate must **REFUSE** (`current_allowed=false`)

The gate emit/validate path is **Rust** (`ha-physics-gate` / Bekker + related thermometers). Python only orchestrates. If the bin is missing, it fails closed (no pure-Python PASS).

**What you get after a run**

- Terminal board with named falsifiers
- JSON receipt + Dual kit (`dual_safe.json` / `dual_hostile.json`)
- Something you can paste into a review thread

**Repo:** https://github.com/StanByriukov02/ha-production-gate  
**Cold path:** `./scripts/bootstrap.sh` (Windows: `.\scripts\bootstrap.ps1`)  
**Method / honesty:** https://github.com/StanByriukov02/ha-production-gate/blob/main/docs/strike/TECH_NOTE_DUAL_REFUSE_V0.md

This is a **soft teaching Dual** on a public lunar_scout-style preset — not field MEASURED, not HIL, not a ROS package yet. The ask is narrow: if you maintain Gazebo/Nav2/MoveIt worlds, does a Dual refuse habit belong in your pre-merge checklist? Happy to take FAIL logs from cold clones.
