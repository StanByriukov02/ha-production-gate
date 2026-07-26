"""Scrub workshop vault paths and DRAFT status from the public gate tree."""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SKIP = {".git", ".venv", "target", "egg-info", ".cursor"}
_VAULT = re.compile(r"06_2BRAIN/[A-Za-z0-9_./\-]+")
_EXTS = {".json", ".py", ".md", ".toml", ".yml", ".yaml", ".txt"}


def scrub_tree(root: Path) -> int:
    n = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(s in p.parts for s in _SKIP):
            continue
        if p.suffix.lower() not in _EXTS:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        out = _VAULT.sub("public_teaching_bind", text)
        out = out.replace('"status": "OPEN_TEACHING"', '"status": "OPEN_TEACHING"')
        out = out.replace("'status': 'OPEN_TEACHING'", "'status': 'OPEN_TEACHING'")
        out = out.replace("SPEC", "SPEC")
        if out != text:
            p.write_text(out, encoding="utf-8")
            n += 1
            print(f"scrubbed {p.relative_to(root).as_posix()}")
    return n


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"files_changed={scrub_tree(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
