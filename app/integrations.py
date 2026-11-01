"""Block 16 — Integrations status for the GUI box (read-only, no secrets).

The Integrations box in the GUI shows, in plain words, what Hive-Mind
is connected to: the MCP transports, the model endpoint, the
Supabase backup, and the EXP total. This module computes that
status from the environment and the vault only. It NEVER returns a
credential: the model key is reported as a boolean (``key_present``)
and nothing else; the Supabase URL is not returned at all, only
whether both Supabase values are set plus the bucket name. Key
values, key fragments, and key-shaped strings must never appear in
this module's output.

The only network use is a best-effort localhost health check for
the SSE server (``http://127.0.0.1:8765/``, short timeout). Any
failure — server not running, connection refused, timeout — means
``running: False``; it never raises, and no remote host is ever
contacted. Nothing here makes a live model or Supabase call, and
nothing here reads a key file: the environment is the only source,
exactly as the live clients read it.

Every failure mode degrades to "not configured" defaults: the
endpoint must never return an exception or a stack trace.
"""

import os
import urllib.error
import urllib.request

from .exp import totals as exp_totals
from .live_clients import live_enabled
from .live_meta import DEFAULT_BASE_URL, DEFAULT_MODEL, _is_loopback_url
from .live_supabase import DEFAULT_BUCKET

STDIO_COMMAND = "python -m app.mcp_server"
SSE_URL = "http://127.0.0.1:8765/sse"
SSE_HEALTH_URL = "http://127.0.0.1:8765/"
SSE_PROBE_TIMEOUT_SECONDS = 0.5


def _sse_running(probe=None):
    """True only if the local SSE server answers its health reply.

    ``probe`` is a test seam: a callable taking the health URL and
    returning a boolean. With no probe, a short-timeout localhost
    GET is attempted; every error means "not running".
    """
    if probe is not None:
        try:
            return bool(probe(SSE_HEALTH_URL))
        except Exception:
            return False
    try:
        with urllib.request.urlopen(
            SSE_HEALTH_URL, timeout=SSE_PROBE_TIMEOUT_SECONDS
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def _model_status():
    """Model endpoint facts: base URL, model, live-vs-fake, key boolean."""
    base_url = (
        os.environ.get("HIVE_MIND_META_BASE_URL") or DEFAULT_BASE_URL
    ).rstrip("/")
    model = os.environ.get("HIVE_MIND_META_MODEL") or DEFAULT_MODEL
    live = live_enabled()
    key_present = bool(os.environ.get("META_API_KEY"))
    # A loopback endpoint (Ollama, local OpenWebUI) needs no key;
    # a remote endpoint refuses without one. The key itself is
    # never included — only whether one is set.
    key_required = not _is_loopback_url(base_url)
    if not live:
        status_word = "Fake (tests only)"
    elif key_present or not key_required:
        status_word = "Connected"
    else:
        status_word = "Not connected"
    return {
        "base_url": base_url,
        "model": model,
        "live": live,
        "key_present": key_present,
        "key_required": key_required,
        "status": status_word,
    }


def _supabase_status():
    """Supabase facts: configured boolean + bucket name only.

    The Supabase URL is deliberately NOT returned: it is not
    needed to show connection state, and returning fewer facts
    keeps the endpoint secret-free by construction.
    """
    configured = bool(
        os.environ.get("SUPABASE_URL")
        and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )
    bucket = os.environ.get("HIVE_MIND_SUPABASE_BUCKET") or DEFAULT_BUCKET
    return {
        "configured": configured,
        "bucket": bucket,
        "status": "Connected" if configured else "Not connected",
    }


def _exp_status(vault_dir):
    """EXP total only. A broken log degrades to zero, never an error."""
    try:
        data = exp_totals(vault_dir)
        return {"total": int(data["total"]), "events": int(data["events"])}
    except Exception:
        return {"total": 0, "events": 0}


def _status(vault_dir, sse_probe=None):
    sse_up = _sse_running(sse_probe)
    return {
        "mcp_stdio": {"command": STDIO_COMMAND, "status": "Available"},
        "mcp_sse": {
            "url": SSE_URL,
            "running": sse_up,
            "status": "Connected" if sse_up else "Not connected",
        },
        "model": _model_status(),
        "supabase": _supabase_status(),
        "exp": _exp_status(vault_dir),
    }


def status(vault_dir, sse_probe=None):
    """Public entry point: never raises, never leaks a secret."""
    try:
        return _status(vault_dir, sse_probe)
    except Exception:
        return {
            "mcp_stdio": {"command": STDIO_COMMAND, "status": "Available"},
            "mcp_sse": {
                "url": SSE_URL,
                "running": False,
                "status": "Not connected",
            },
            "model": {
                "base_url": DEFAULT_BASE_URL,
                "model": DEFAULT_MODEL,
                "live": False,
                "key_present": False,
                "key_required": True,
                "status": "Fake (tests only)",
            },
            "supabase": {
                "configured": False,
                "bucket": DEFAULT_BUCKET,
                "status": "Not connected",
            },
            "exp": {"total": 0, "events": 0},
        }
