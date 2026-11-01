"""Block 12 — MCP over server-sent events (SSE), stdlib only.

The same 8 tools, the same JSON-RPC 2.0 handling, a different
transport: clients that cannot speak stdio (browser-based clients,
remote editors, OpenWebUI-style front ends) connect here instead.
Tool logic is NOT forked: every request goes through
``app.mcp_server.handle_request``, the exact function the stdio
server uses, with the same flat-scalar argument rule and the same
``tools/list`` / ``tools/call`` shapes.

Protocol (the MCP SSE shape used by other MCP servers):

* ``GET /sse`` opens one event stream and immediately sends an
  ``endpoint`` event naming this connection's POST URL, which
  carries a per-connection session id:
  ``event: endpoint`` / ``data: /messages?session_id=<id>``.
* ``POST /messages?session_id=<id>`` takes one JSON-RPC request
  body and returns 202 at once; the response arrives on the open
  stream as a ``message`` event. A POST with a missing or unknown
  session id gets 404 and nothing is queued.
* The stream stays open with a ``: ping`` comment every 25 seconds
  of silence so proxies do not close it. Closing the stream drops
  the session; a later POST to that id gets 404.

Localhost only by default (``127.0.0.1``). This server makes no
outbound call of its own: the only network activity is serving
local clients. The fake clients stay the default behind the
tools; live endpoints are used only when the env-gated factory
in ``app/live_clients.py`` opts in, exactly as with stdio.

Run: ``python -m app.sse_server`` (port 8765) or
``python -m app.sse_server --port 9000``.
"""

import argparse
import json
import queue
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import SERVER_NAME, VERSION
from .mcp_server import handle_request

_HEARTBEAT_SECONDS = 25


class _Session:
    """One open event stream, fed by a queue the POST side fills."""

    def __init__(self):
        self.messages = queue.Queue()


_SESSIONS = {}
_SESSIONS_LOCK = threading.Lock()


def _new_session():
    session_id = uuid.uuid4().hex
    with _SESSIONS_LOCK:
        _SESSIONS[session_id] = _Session()
    return session_id


def _drop_session(session_id):
    with _SESSIONS_LOCK:
        _SESSIONS.pop(session_id, None)


def _session(session_id):
    with _SESSIONS_LOCK:
        return _SESSIONS.get(session_id)


def _session_id_from_path(path):
    """The session_id query value, parsed by hand (no URL library)."""
    if "?" not in path:
        return ""
    query = path.split("?", 1)[1]
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            if key == "session_id":
                return value
    return ""


class _SSEHandler(BaseHTTPRequestHandler):
    # HTTP/1.1 so one long-lived stream stays open on a persistent
    # connection; every non-stream reply carries a Content-Length.
    protocol_version = "HTTP/1.1"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_event(self, event, data):
        self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def do_GET(self):  # noqa: N802 - http.server naming
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_json(200, {
                "name": SERVER_NAME,
                "version": VERSION,
                "transport": "sse",
                "endpoints": ["/sse", "/messages"],
            })
            return
        if path != "/sse":
            self.send_error(404)
            return
        session_id = _new_session()
        session = _session(session_id)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self._send_event("endpoint", f"/messages?session_id={session_id}")
            while True:
                try:
                    message = session.messages.get(timeout=_HEARTBEAT_SECONDS)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self._send_event("message", message)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _drop_session(session_id)

    def do_POST(self):  # noqa: N802 - http.server naming
        path = self.path.split("?", 1)[0]
        if path != "/messages":
            self.send_error(404)
            return
        session = _session(_session_id_from_path(self.path))
        if session is None:
            self.send_error(404, "unknown session_id")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            request = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            request = None
        if request is None:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700,
                                  "message": "Parse error: expected one JSON object"}}
        else:
            response = handle_request(request)
        if response is not None:
            session.messages.put(json.dumps(response))
        self.send_response(202)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):  # keep the SSE server quiet
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Hive-Mind MCP server over SSE (localhost only)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), _SSEHandler)
    print(f"Hive-Mind MCP SSE at http://{args.host}:{args.port}/sse "
          "(localhost only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
