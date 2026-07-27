"""Fetch prebuilt Dual oracle bins from GitHub Releases (no Cargo required).

Downloads `bins-latest` assets into `target/release/` so existing find_*_bin
paths work. Falls back to a clear cargo hint if the release is missing.

TABU: pure-Python oracle substitute · soft-mint PASS without bins.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import ssl
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_OUT = _REPO / "target" / "release"
_DEFAULT_REPO = "StanByriukov02/ha-production-gate"
_DEFAULT_TAG = "bins-latest"
SCHEMA = "ha_ensure_bins_v1"

_BIN_STEMS = (
    "ha-physics-gate",
    "ha-silicon-fuse",
    "ha-energy-ledger",
    "ha-body-identity",
    "manipulator_kinematics_step",
)


def platform_id() -> str:
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64", "x64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        arch = "aarch64"
    else:
        arch = machine
    if sysname == "windows":
        return f"windows-{arch}"
    if sysname == "darwin":
        return f"macos-{arch}"
    if sysname == "linux":
        return f"linux-{arch}"
    return f"{sysname}-{arch}"


def _exe(stem: str) -> str:
    return stem + (".exe" if sys.platform == "win32" else "")


def local_bins_present(*, out: Path | None = None) -> list[str]:
    root = out or _OUT
    missing: list[str] = []
    for stem in _BIN_STEMS:
        if not (root / _exe(stem)).is_file():
            missing.append(_exe(stem))
    return missing


def asset_name(plat: str | None = None) -> str:
    return f"ha-bins-{plat or platform_id()}.zip"


def release_asset_url(
    *,
    github_repo: str = _DEFAULT_REPO,
    tag: str = _DEFAULT_TAG,
    plat: str | None = None,
) -> str:
    return (
        f"https://github.com/{github_repo}/releases/download/{tag}/{asset_name(plat)}"
    )


def _download(url: str, *, timeout: float = 120.0) -> bytes:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ha-production-gate-ensure-bins/0.1"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return resp.read()


def ensure_bins(
    *,
    force: bool = False,
    github_repo: str | None = None,
    tag: str | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Ensure Dual oracle bins exist under target/release/.

    Order: already present → download bins-latest → error with cargo hint.
    """
    repo = (github_repo or os.environ.get("HA_BINS_REPO") or _DEFAULT_REPO).strip()
    rel_tag = (tag or os.environ.get("HA_BINS_TAG") or _DEFAULT_TAG).strip()
    out = out_dir or _OUT
    plat = platform_id()
    missing = local_bins_present(out=out)
    if not missing and not force:
        return {
            "schema": SCHEMA,
            "ok": True,
            "action": "already_present",
            "platform": plat,
            "out_dir": str(out),
            "bins": [_exe(s) for s in _BIN_STEMS],
        }

    url = release_asset_url(github_repo=repo, tag=rel_tag, plat=plat)
    try:
        blob = _download(url)
    except urllib.error.HTTPError as exc:
        return {
            "schema": SCHEMA,
            "ok": False,
            "action": "download_failed",
            "platform": plat,
            "url": url,
            "error": f"HTTP {exc.code}",
            "hint": (
                "Prebuilt bins not published for this platform yet. "
                "Install Rust and run ./scripts/bootstrap.sh "
                "or: cargo build -p ha_physics_gate --release "
                "(and the other four Dual bins)."
            ),
        }
    except urllib.error.URLError as exc:
        return {
            "schema": SCHEMA,
            "ok": False,
            "action": "download_failed",
            "platform": plat,
            "url": url,
            "error": str(exc.reason if hasattr(exc, "reason") else exc),
            "hint": "Network failed fetching bins-latest. Use cargo bootstrap or retry.",
        }

    out.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if not name or name.endswith("/"):
                continue
            # Only oracle stems
            stem = name[:-4] if name.lower().endswith(".exe") else name
            if stem not in _BIN_STEMS and name not in {_exe(s) for s in _BIN_STEMS}:
                continue
            target = out / name
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            if sys.platform != "win32":
                target.chmod(target.stat().st_mode | 0o111)
            extracted.append(name)

    still = local_bins_present(out=out)
    ok = len(still) == 0
    return {
        "schema": SCHEMA,
        "ok": ok,
        "action": "downloaded",
        "platform": plat,
        "url": url,
        "out_dir": str(out),
        "extracted": extracted,
        "missing_after": still,
        "bytes": len(blob),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ha-ensure-bins",
        description="Download Dual oracle bins from GitHub bins-latest (skip Cargo when possible)",
    )
    p.add_argument("--force", action="store_true", help="Re-download even if bins exist")
    p.add_argument("--repo", default=None, help="owner/name (default StanByriukov02/ha-production-gate)")
    p.add_argument("--tag", default=None, help="release tag (default bins-latest)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    doc = ensure_bins(force=bool(args.force), github_repo=args.repo, tag=args.tag)
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        if doc.get("ok") and doc.get("action") == "already_present":
            print(f"bins already present under {doc.get('out_dir')} ({doc.get('platform')})")
        elif doc.get("ok"):
            print(f"downloaded {doc.get('platform')} bins -> {doc.get('out_dir')}")
            print("extracted:", ", ".join(doc.get("extracted") or []))
        else:
            print(f"ensure-bins FAILED ({doc.get('error')})", file=sys.stderr)
            print(doc.get("hint") or "", file=sys.stderr)
            print(f"url: {doc.get('url')}", file=sys.stderr)
            return 1
    return 0 if doc.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
