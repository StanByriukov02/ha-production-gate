"""Body identity v1 — thin Python orchestration over Rust ha-body-identity.

TABU: Python hashlib as production oracle. All SHA-256 goes through the Rust binary.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_BIN_STEM = "ha-body-identity"
SCHEMA = "body_identity_v1"
IDENTITY_FILENAME = "BODY_IDENTITY_v1.json"


class BodyIdentityError(ValueError):
    """Raised when body identity is missing or does not match on-disk bytes."""


def _exe_name() -> str:
    return _BIN_STEM + (".exe" if sys.platform == "win32" else "")


def find_ha_body_identity_bin() -> Path:
    """Resolve Rust binary: HA_BODY_IDENTITY_BIN → release → debug."""
    env = (os.environ.get("HA_BODY_IDENTITY_BIN") or "").strip()
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(
                f"HA_BODY_IDENTITY_BIN set but not a file: {p} "
                "(no pure-Python hash fallback)"
            )
        return p.resolve()
    name = _exe_name()
    for candidate in (
        _REPO / "target" / "release" / name,
        _REPO / "target" / "debug" / name,
    ):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "ha-body-identity binary missing — set HA_BODY_IDENTITY_BIN or "
        "cargo build -p ha_body_identity --release "
        "(no pure-Python hash fallback for production path)"
    )


# Alias used by tests / older call sites
resolve_ha_body_identity_bin = find_ha_body_identity_bin


def binary_available() -> bool:
    try:
        find_ha_body_identity_bin()
        return True
    except FileNotFoundError:
        return False


def _run_cli(args: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    from dogfood_platform.win_hidden_subprocess_v1 import hidden_run_kwargs

    bin_path = find_ha_body_identity_bin()
    return subprocess.run(
        [str(bin_path), *args],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        **hidden_run_kwargs(),
    )


def compute_body_sha256(path: str | Path) -> str:
    """SHA-256 hex of file bytes via Rust `hash --file`. No Python hashlib."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"body file not found for hash: {p}")
    proc = _run_cli(["hash", "--file", str(p)])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-body-identity hash failed: {err}")
    digest = (proc.stdout or "").strip().splitlines()[-1].strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError(f"ha-body-identity hash returned non-hex digest: {digest!r}")
    return digest


def validate_body_identity_json(doc: dict[str, Any] | str | Path) -> None:
    """Validate body_identity_v1 via Rust `validate --json`."""
    if isinstance(doc, Path):
        json_path = doc
        if not json_path.is_file():
            raise FileNotFoundError(f"identity json not found: {json_path}")
    else:
        import tempfile

        payload = doc if isinstance(doc, str) else json.dumps(doc, indent=2, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(payload if payload.endswith("\n") else payload + "\n")
            json_path = Path(tmp.name)
        try:
            _validate_json_path(json_path)
        finally:
            json_path.unlink(missing_ok=True)
        return
    _validate_json_path(json_path)


def _validate_json_path(json_path: Path) -> None:
    proc = _run_cli(["validate", "--json", str(json_path)])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise BodyIdentityError(f"body_identity validate FAIL: {err}")


def emit_body_identity(
    path: str | Path,
    *,
    kind: str,
    source_name: str,
    chain_id: str | None = None,
    root_link: str | None = None,
    ee_link: str | None = None,
) -> dict[str, Any]:
    """Emit body_identity_v1 via Rust `emit`, then validate (optional extra fields merged)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"body file not found for emit: {p}")
    args = [
        "emit",
        "--file",
        str(p),
        "--kind",
        str(kind),
        "--source-name",
        str(source_name),
    ]
    if chain_id:
        args.extend(["--chain-id", str(chain_id)])
    proc = _run_cli(args)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"ha-body-identity emit failed: {err}")
    identity = json.loads(proc.stdout)
    if root_link:
        identity["root_link"] = str(root_link)
    if ee_link:
        identity["ee_link"] = str(ee_link)
    validate_body_identity_json(identity)
    return identity


def identity_path_for_project(project_id: str) -> Path:
    from dogfood_platform.robot_project_desk_v1 import project_dir

    return project_dir(project_id) / "body" / IDENTITY_FILENAME


def resolve_body_bytes_path(project_id: str, body: dict[str, Any] | None = None) -> Path:
    """Resolve on-disk body bytes under project body/ (stored_file or manifest.json)."""
    from dogfood_platform.robot_project_desk_v1 import project_dir

    root = project_dir(project_id)
    body_dir = root / "body"
    if body is None:
        from dogfood_platform.robot_project_desk_v1 import get_project

        body = (get_project(project_id).get("body") or {}) if project_id else {}
    stored = str((body or {}).get("stored_file") or "").strip()
    if stored:
        candidate = root / stored if not Path(stored).is_absolute() else Path(stored)
        if candidate.is_file():
            return candidate
    # Fallback: durable manifest is the body artifact (presets / recipe)
    manifest = body_dir / "manifest.json"
    if manifest.is_file():
        return manifest
    raise FileNotFoundError(f"no stored body bytes under {body_dir} for project {project_id}")


def write_body_identity_artifact(
    project_id: str,
    body_file: str | Path,
    *,
    kind: str,
    source_name: str,
    chain_id: str | None = None,
    root_link: str | None = None,
    ee_link: str | None = None,
    embed_in_manifest: bool = True,
) -> dict[str, Any]:
    """Emit via Rust and write body/BODY_IDENTITY_v1.json.

    When embed_in_manifest and the hashed file is not body/manifest.json,
    also writes identity into body/manifest.json (safe — does not change hashed bytes).
    If the hashed file IS the manifest (preset), identity is NOT inlined into it
    (self-hash would loop); callers keep identity on project.body + BODY_IDENTITY_v1.json.
    """
    from dogfood_platform.robot_project_desk_v1 import project_dir

    identity = emit_body_identity(
        body_file,
        kind=kind,
        source_name=source_name,
        chain_id=chain_id,
        root_link=root_link,
        ee_link=ee_link,
    )
    out = identity_path_for_project(project_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(identity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validate_body_identity_json(out)

    body_path = Path(body_file).resolve()
    manifest_path = (project_dir(project_id) / "body" / "manifest.json").resolve()
    if embed_in_manifest and manifest_path.is_file() and body_path != manifest_path:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        if isinstance(manifest, dict):
            manifest["identity"] = identity
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    return identity


def write_body_identity_for_stored_file(
    body_dir: str | Path,
    body_file: str | Path,
    *,
    kind: str,
    source_name: str,
    chain_id: str | None = None,
    root_link: str | None = None,
    ee_link: str | None = None,
) -> dict[str, Any]:
    """Compat: write BODY_IDENTITY under body_dir (project body/)."""
    body_dir_p = Path(body_dir)
    # body_dir is .../<project_id>/body — project_id is parent name
    project_id = body_dir_p.parent.name
    return write_body_identity_artifact(
        project_id,
        body_file,
        kind=kind,
        source_name=source_name,
        chain_id=chain_id,
        root_link=root_link,
        ee_link=ee_link,
    )


def load_body_identity(project_id: str) -> dict[str, Any] | None:
    """Load identity from BODY_IDENTITY_v1.json, else project body / manifest embed."""
    from dogfood_platform.robot_project_desk_v1 import get_project, project_dir

    path = identity_path_for_project(project_id)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    doc = get_project(project_id)
    body = doc.get("body")
    if isinstance(body, dict) and isinstance(body.get("identity"), dict):
        return body["identity"]
    manifest_path = project_dir(project_id) / "body" / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(manifest.get("identity"), dict):
            return manifest["identity"]
    return None


def check_body_identity_on_project(project_id: str) -> dict[str, Any]:
    """Non-raising check. When body present: identity required + hash match via Rust."""
    from dogfood_platform.robot_project_desk_v1 import get_project

    doc = get_project(project_id)
    body = doc.get("body")
    if not body:
        return {
            "ok": True,
            "skipped": True,
            "verdict": "SKIP",
            "errors": [],
            "note": "no body attached",
        }
    errors: list[str] = []
    identity = load_body_identity(project_id)
    if not isinstance(identity, dict) or not identity:
        return {
            "ok": False,
            "skipped": False,
            "verdict": "FAIL",
            "errors": ["missing_body_identity"],
            "identity": None,
        }
    try:
        validate_body_identity_json(identity)
    except (BodyIdentityError, FileNotFoundError, RuntimeError) as exc:
        errors.append("missing_body_identity")
        errors.append(str(exc))
        return {
            "ok": False,
            "skipped": False,
            "verdict": "FAIL",
            "errors": errors,
            "identity": identity,
        }
    try:
        body_path = resolve_body_bytes_path(project_id, body if isinstance(body, dict) else None)
        got = compute_body_sha256(body_path)
    except (FileNotFoundError, RuntimeError) as exc:
        return {
            "ok": False,
            "skipped": False,
            "verdict": "FAIL",
            "errors": ["missing_body_identity", str(exc)],
            "identity": identity,
        }
    expected = str(identity.get("body_sha256") or "").strip().lower()
    if got != expected:
        errors.append("body_identity_mismatch")
    bytes_len = identity.get("bytes_len")
    if bytes_len is not None:
        actual_len = body_path.stat().st_size
        if int(bytes_len) != int(actual_len):
            if "body_identity_mismatch" not in errors:
                errors.append("body_identity_mismatch")
    ok = not errors
    return {
        "ok": ok,
        "skipped": False,
        "verdict": "PASS" if ok else "FAIL",
        "errors": errors,
        "identity": identity,
        "body_path": str(body_path),
        "computed_sha256": got,
    }


def require_body_identity_on_project(project_id: str) -> dict[str, Any]:
    """Hard gate: body present ⇒ identity block matches hashed body bytes on disk."""
    verdict = check_body_identity_on_project(project_id)
    if not verdict["ok"]:
        raise BodyIdentityError(
            "BODY_IDENTITY FAIL — "
            + ", ".join(verdict.get("errors") or ["unknown"])
        )
    return verdict
