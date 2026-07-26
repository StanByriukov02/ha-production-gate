# Channel 3 — Show HN

**Paste title + text as-is.** Optional: Lobsters with the same body, tag `show` / `programming`.

---

## Title

```text
Show HN: Production Gate – Dual Safe/Hostile physics refuse (Rust oracle)
```

## Text

```text
I built a small cloneable ritual for robot / autonomy physics claims.

Problem: a stack can look healthy forever if it only ever runs in a friendly world.

This CLI runs the same teaching stack twice:

  Safe   → physics gate must ALLOW
  Hostile → same gate must REFUSE

The gate boolean is emitted/validated by Rust (ha-physics-gate). Python is glue only;
missing bin ⇒ fail closed (no pure-Python PASS).

You get a PASS/FAIL board, JSON receipt, and Dual kit files another engineer can re-read.

Repo: https://github.com/StanByriukov02/ha-production-gate
Cold path: ./scripts/bootstrap.sh   (Windows: .\scripts\bootstrap.ps1)
Expect: PRODUCTION_GATE_RITUAL_PASS

Method + honesty (soft teaching Dual · not field MEASURED · not HIL):
https://github.com/StanByriukov02/ha-production-gate/blob/main/docs/strike/TECH_NOTE_DUAL_REFUSE_V0.md

Examples walkthroughs: /docs/examples/

Not a ROS node yet and not a GUI install — the screenshot on the README is a companion Dual desk visual; the supported path is the CLI ritual. CI on main builds the bins and runs the same gate.
```

## Reply bank (keep short)

| They say | You say |
|----------|---------|
| Is this MEASURED / certified? | No — soft teaching Dual. Named ε on the receipt. See tech note Honesty. |
| Where is the GUI? | Companion desk is visual only. Clone path is `ha-production-gate` CLI. |
| Why Rust? | So the gate cannot soft-mint PASS in Python when the oracle bin is gone. |
| ROS? | Not a package yet. Gate is the refuse habit; bridge is next if people run it cold. |
| Show me FAIL | Rename/remove `ha-physics-gate` and re-run — should hard-fail. Or Hostile must refuse on Dual. |
