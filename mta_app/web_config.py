from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

SETTINGS_PATH = Path("settings.json")


def _load_settings_text() -> str:
    return SETTINGS_PATH.read_text(encoding="utf-8")


def _save_settings_text(text: str) -> None:
    SETTINGS_PATH.write_text(text, encoding="utf-8")


HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>MTA Stations Config</title></head>
<body style="font-family: sans-serif; max-width: 900px; margin: 20px auto;">
  <h2>MTA Stations Config</h2>
  <p>Edit settings.json and click Save. (Be careful: invalid JSON will be rejected.)</p>
  <form method="POST" action="/save">
    <textarea name="json" style="width: 100%; height: 520px;">{json_text}</textarea><br><br>
    <button type="submit">Save</button>
  </form>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_response(404)
            self.end_headers()
            return

        try:
            text = _load_settings_text()
            page = HTML.format(json_text=text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def do_POST(self):
        if self.path != "/save":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body)
        json_text = form.get("json", [""])[0]

        try:
            # validate JSON
            json.loads(json_text)
            _save_settings_text(json_text)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Saved. You can go back.")
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Invalid JSON: {e}".encode("utf-8"))


class WebConfigServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8088):
        self.host = host
        self.port = port
        self._httpd = HTTPServer((host, port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=2.0)
