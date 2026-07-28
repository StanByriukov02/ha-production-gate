"""CLI workbench for owned Dual soils — template / duplicate / validate.

Not MEASURED. Teaching catalog ids firm_lab/soft_hostile forbidden as «мои».
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from production_gate.dual_owned_soils_v1 import (
    SCHEMA,
    dump_owned_soils_pack,
    duplicate_soil,
    load_owned_soils,
    make_owned_soils_template,
    parse_owned_soils_doc,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ha-soils",
        description="Owned Dual soils workbench (template · duplicate · validate)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="Write a blank owned soils pack")
    t.add_argument("--out", type=str, required=True)
    t.add_argument("--safe-id", default="my_firm")
    t.add_argument("--hostile-id", default="my_soft")
    t.add_argument("--g", type=float, default=9.81)

    d = sub.add_parser("duplicate", help="Duplicate one soil row inside a pack")
    d.add_argument("--pack", type=str, required=True)
    d.add_argument("--from-id", dest="from_id", required=True)
    d.add_argument("--as-id", dest="as_id", required=True)
    d.add_argument("--set-as", choices=("safe", "hostile"), default=None)
    d.add_argument("--out", type=str, required=True)

    v = sub.add_parser("validate", help="Validate an owned soils pack")
    v.add_argument("--pack", type=str, required=True)

    args = p.parse_args(argv)
    try:
        if args.cmd == "template":
            pack = make_owned_soils_template(
                safe_id=args.safe_id,
                hostile_id=args.hostile_id,
                g_mps2=args.g,
            )
            out = Path(args.out).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(dump_owned_soils_pack(pack), encoding="utf-8")
            parse_owned_soils_doc(pack, path=str(out))
            print(json.dumps({"ok": True, "schema": SCHEMA, "out": str(out)}))
            return 0

        if args.cmd == "duplicate":
            src = Path(args.pack).expanduser()
            doc = json.loads(src.read_text(encoding="utf-8"))
            out_doc = duplicate_soil(
                doc,
                source_id=args.from_id,
                new_id=args.as_id,
                set_as=args.set_as,
            )
            parse_owned_soils_doc(out_doc)
            dest = Path(args.out).expanduser()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(dump_owned_soils_pack(out_doc), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "ok": True,
                        "out": str(dest),
                        "from": args.from_id,
                        "as": args.as_id,
                        "set_as": args.set_as,
                    }
                )
            )
            return 0

        if args.cmd == "validate":
            pack = load_owned_soils(args.pack)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "schema": pack["schema"],
                        "safe": pack["safe_soil_id"],
                        "hostile": pack["hostile_soil_id"],
                        "g_mps2": pack["g_mps2"],
                        "soil_ids": sorted(pack["soils"].keys()),
                    }
                )
            )
            return 0
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
