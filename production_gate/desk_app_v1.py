"""Local Dual desk — one job: pick a body, run Safe/Hostile, read the board.

Serves desk/index.html on localhost. No cloud. Soft teaching Dual.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_REPO = Path(__file__).resolve().parents[1]
_DESK_DIR = _REPO / "desk"
_DEFAULT_PORT = 8765


def _json_bytes(doc: dict[str, Any], code: int = 200) -> tuple[int, bytes, str]:
    raw = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    return code, raw, "application/json; charset=utf-8"


class DeskHandler(BaseHTTPRequestHandler):
    server_version = "HADualDesk/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            target = _DESK_DIR / "index.html"
            if not target.is_file():
                self._send(404, b"desk/index.html missing\n", "text/plain")
                return
            data = target.read_bytes()
            self._send(200, data, "text/html; charset=utf-8")
            return
        if path == "/api/presets":
            from production_gate.robot_project_desk_v1 import PRESETS

            rows = [
                {"id": k, "label": v.get("label"), "blurb": v.get("blurb"), "kind": v.get("kind")}
                for k, v in PRESETS.items()
            ]
            code, raw, ct = _json_bytes({"ok": True, "presets": rows})
            self._send(code, raw, ct)
            return
        if path == "/api/health":
            code, raw, ct = _json_bytes(
                {
                    "ok": True,
                    "app": "ha-dual-desk",
                    "version": "0.2.0",
                    "honesty": {
                        "local_only": True,
                        "not_measured": True,
                        "pass_not_required": True,
                    },
                }
            )
            self._send(code, raw, ct)
            return
        # static under desk/
        rel = path.lstrip("/").replace("..", "")
        target = (_DESK_DIR / rel).resolve()
        if not str(target).startswith(str(_DESK_DIR.resolve())) or not target.is_file():
            self._send(404, b"not found\n", "text/plain")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw_in = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw_in.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            code, raw, ct = _json_bytes({"ok": False, "error": "invalid_json"}, 400)
            self._send(code, raw, ct)
            return

        if path == "/api/dual":
            try:
                from production_gate.dual_socket_v1 import run_dual_socket

                preset = payload.get("preset")
                urdf_text = payload.get("urdf_text")
                urdf_name = str(payload.get("urdf_name") or "upload.urdf")
                soils_text = payload.get("soils_text")
                soils_name = str(payload.get("soils_name") or "owned_soils.json")
                model_kind = payload.get("kind") or payload.get("model_kind") or "wheeled_base"
                soils_path: str | None = None
                if soils_text:
                    soils_dir = _REPO / "results" / "runtime" / "byo_soils"
                    soils_dir.mkdir(parents=True, exist_ok=True)
                    safe_s = "".join(
                        c if c.isalnum() or c in "._-" else "_" for c in soils_name
                    )[:120]
                    sdest = soils_dir / (safe_s or "owned_soils.json")
                    sdest.write_text(str(soils_text), encoding="utf-8")
                    soils_path = str(sdest)
                if urdf_text:
                    scratch = _REPO / "results" / "runtime" / "byo_urdf"
                    scratch.mkdir(parents=True, exist_ok=True)
                    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in urdf_name)[:120]
                    dest = scratch / (safe or "upload.urdf")
                    dest.write_text(str(urdf_text), encoding="utf-8")
                    doc = run_dual_socket(
                        urdf=str(dest),
                        soils=soils_path,
                        model_kind=str(model_kind),
                        mass_kg=payload.get("mass_kg"),
                        n_contacts=payload.get("n_contacts"),
                        contact_width_m=payload.get("contact_width_m"),
                        contact_length_m=payload.get("contact_length_m"),
                        root_link=str(payload.get("root_link") or "base_link"),
                        ee_link=payload.get("ee_link"),
                    )
                else:
                    doc = run_dual_socket(
                        preset=str(preset or "open_diffbot"),
                        soils=soils_path,
                    )
                code, raw, ct = _json_bytes(
                    {"ok": doc.get("verdict") == "DUAL_SOCKET_PASS", **doc}
                )
                self._send(code, raw, ct)
            except Exception as exc:  # noqa: BLE001
                code, raw, ct = _json_bytes({"ok": False, "error": str(exc)}, 500)
                self._send(code, raw, ct)
            return

        code, raw, ct = _json_bytes({"ok": False, "error": "unknown_route"}, 404)
        self._send(code, raw, ct)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ha-desk", description="Local Dual desk (localhost)")
    p.add_argument("--port", type=int, default=_DEFAULT_PORT)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)

    if not (_DESK_DIR / "index.html").is_file():
        print(f"missing {_DESK_DIR / 'index.html'}", file=sys.stderr)
        return 2

    host = "127.0.0.1"
    httpd = ThreadingHTTPServer((host, int(args.port)), DeskHandler)
    url = f"http://{host}:{int(args.port)}/"
    print(f"HA Dual desk → {url}", flush=True)
    print("Soft teaching Dual · local only · Ctrl+C to stop", flush=True)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ndesk stopped", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
