"""Block 1 MCP server: stdio, JSON-RPC 2.0, standard library only.

No MCP SDK, no HTTP framework, no network: the server reads one JSON
object per line from stdin and writes one JSON response per line to
stdout. That is the whole transport, and it is enough for any MCP
client that speaks stdio (Codex, Claude Code, and friends all do).

Supported methods: ``initialize``, ``ping``, ``tools/list``,
``tools/call``. Notifications (``notifications/*``) get no reply, per
JSON-RPC. Unknown methods get -32601, malformed JSON gets -32700, bad
arguments get -32602. The process exits cleanly on EOF: it blocks on
stdin and does no polling (Pillar 2).

SSE is intentionally NOT in Block 1: it needs an HTTP transport the
stdlib server does not provide, and the game plan puts it after the
foundation. Stdio is the Block 1 transport; the same tool registry
serves SSE when a later block adds it.

Block 1 behaviour for tools/call: every tool returns the clear
``not_implemented`` stub from :mod:`app.tools`. Arguments must be flat
scalars (string/integer/number/boolean/null) — a nested dict or list
is rejected with -32602, per the spec's flat-argument rule.
"""

import argparse
import json
import sys

from .config import SERVER_NAME, VERSION
from .dispatch import dispatch_tool
from .tools import TOOLS, get_tool

_SCALAR_TYPES = (str, int, float, bool, type(None))


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _record_client_info(request, client_context):
    """Best-effort recording of the client's `initialize` clientInfo.

    ``client_context`` is a dict owned by the caller (one per
    connection: the stdio loop owns one, each SSE session owns
    one). A missing, malformed, or nameless clientInfo leaves the
    name "unknown" — recording never fails a request. Only the
    client's own name/version are kept, nothing else.
    """
    if client_context is None:
        return
    name = "unknown"
    version = ""
    try:
        params = request.get("params")
        info = params.get("clientInfo") if isinstance(params, dict) else None
        if isinstance(info, dict):
            raw_name = info.get("name")
            if isinstance(raw_name, str) and raw_name.strip():
                name = raw_name.strip()
            raw_version = info.get("version")
            if isinstance(raw_version, str):
                version = raw_version.strip()
    except Exception:
        pass
    client_context["client_name"] = name
    client_context["client_version"] = version


def handle_request(request, client_context=None):
    """Handle one parsed JSON-RPC request. Returns a response dict or None.

    ``client_context`` is a caller-owned dict (one per connection)
    where the client's `initialize` clientInfo name is recorded
    (Block 17); later tools/call requests on the same connection
    pass that name into capture provenance. Callers that pass none
    get a throwaway context, so direct calls behave exactly as
    before.
    """
    if not isinstance(request, dict):
        return _error(None, -32600, "Invalid Request: expected a JSON object")
    method = request.get("method")
    request_id = request.get("id")
    is_notification = request_id is None
    if client_context is None:
        client_context = {}

    if method == "initialize":
        _record_client_info(request, client_context)
        if is_notification:
            return None
        return _result(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": VERSION},
        })
    if method == "ping":
        return None if is_notification else _result(request_id, {})
    if method and method.startswith("notifications/"):
        return None
    if method == "tools/list":
        if is_notification:
            return None
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        if is_notification:
            return None
        params = request.get("params")
        if not isinstance(params, dict):
            return _error(request_id, -32602, "tools/call params must be an object")
        name = params.get("name")
        tool = get_tool(name) if isinstance(name, str) else None
        if tool is None:
            return _error(request_id, -32602, f"unknown tool: {name!r}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "arguments must be an object")
        for arg_name, value in arguments.items():
            if not isinstance(value, _SCALAR_TYPES):
                return _error(
                    request_id, -32602,
                    f"argument {arg_name!r} must be a flat scalar, "
                    "not a nested object or list",
                )
        missing = [
            arg for arg in tool["inputSchema"]["required"]
            if arg not in arguments
        ]
        if missing:
            return _error(
                request_id, -32602,
                f"missing required argument(s): {', '.join(missing)}",
            )
        payload, is_error = dispatch_tool(
            name, arguments,
            client_name=client_context.get("client_name", "unknown"))
        return _result(request_id, {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "isError": is_error,
        })
    if is_notification:
        return None
    return _error(request_id, -32601, f"Method not found: {method}")


def serve_stdio():
    """Read stdin lines until EOF, writing one response line each.

    One client context for the process lifetime: stdio is a
    single connection, so the `initialize` clientInfo recorded
    here names every capture that follows on it.
    """
    client_context = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = _error(None, -32700, "Parse error: expected one JSON object per line")
        else:
            response = handle_request(request, client_context)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hive-Mind MCP server (Block 1, stdio)")
    parser.add_argument("--stdio", action="store_true", help="Serve MCP over stdio (default)")
    parser.add_argument("--list-tools", action="store_true",
                        help="Print the tools/list payload as JSON and exit")
    args = parser.parse_args(argv)
    if args.list_tools:
        print(json.dumps({"tools": TOOLS}, indent=2))
        return 0
    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
