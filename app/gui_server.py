"""Optional GUI server (Block 6): stdlib only, localhost only.

Serves the static GUI in gui/ plus two live JSON endpoints backed by
the local Store: /api/memories (graph payload) and /api/changelog.
Nothing polls: the GUI fetches once on load and on explicit refresh.
This server is optional — the GUI also works from a static export
(gui/data.json) with no server at all. Not used by any test that
needs the MCP server; the server test starts it on an ephemeral
localhost port and shuts it down.
"""

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .gui_export import export_data
from .store import Store


class _Handler(BaseHTTPRequestHandler):
    gui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - http.server naming
        if self.path in ("/api/memories", "/api/changelog"):
            store = Store()
            try:
                payload = export_data(store)
            finally:
                store.close()
            data = payload if self.path == "/api/memories" else {"changelog": payload["changelog"]}
            self._send(200, json.dumps(data).encode("utf-8"), "application/json")
            return
        # Serve static GUI files from gui/, never outside it.
        path = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        gui_root = os.path.abspath(self.gui_dir)
        target = os.path.normpath(os.path.join(gui_root, path))
        if not target.startswith(gui_root):
            self.send_error(404)
            return
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.exists(target):
            self.send_error(404)
            return
        with open(target, "rb") as f:
            body = f.read()
        content_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
        self._send(200, body, content_type)

    def log_message(self, *args):  # keep the GUI server quiet
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hive-Mind GUI server (localhost only)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"Hive-Mind GUI at http://{args.host}:{args.port}/ (localhost only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
