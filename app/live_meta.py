"""LIVE Meta Model API client (env-gated; NEVER the default).

This module makes real HTTP calls to the Meta Model API, but only
when the caller has explicitly opted in: the factory in
``app/live_clients.py`` returns this client only when
``HIVE_MIND_LIVE=1`` and ``META_API_KEY`` is present in the
environment. Every other path in the codebase uses the fake client
(``app/fake_meta.py``), and importing this module alone makes no
network call.

Rules this client follows, without exception:

* The API key is read from the ``META_API_KEY`` environment variable
  only. It is never read from a file, never logged, never included
  in a request body or an error message, and never echoed back. The
  only place it appears is the ``Authorization`` header.
* The scrubber (``app/scrubber.py``) runs before any payload is
  sent. If it traps anything, the call is refused and no HTTP
  request is made, and the refusal does not consume call budget.
* Hard call budget: at most 5 live calls per process by default.
  The budget can be lowered with ``HIVE_MIND_LIVE_MAX_CALLS``. It can
  only be raised past 5 when ``HIVE_MIND_LIVE_UNSAFE_RAISE_BUDGET=1``
  is also set, which is documented as unsafe: it removes the only
  guard between a runaway loop and the card on file. There is no
  retry loop: one attempt, then an error dict.
* On a missing key, a budget refusal, an HTTP error, or an
  unparseable model response, the client returns a clear error
  dict (``verdict: "error"`` for ``verify``) — never a fake success.
  Callers must check for the ``"error"`` key; ``crosshatch_verify``
  turns it into a ``status: "error"`` payload and stores nothing.

Request shape: the OpenAI-compatible chat-completions convention
for the Meta Model API — ``POST {base_url}/chat/completions`` with
``model``, ``messages``, ``temperature``, and ``max_tokens``. The
endpoint, model, and headers are the documented defaults; the
endpoint and model are configurable via
``HIVE_MIND_META_BASE_URL`` / ``HIVE_MIND_META_MODEL`` because the
repo and its docs do not pin them beyond the defaults stated here.
If Meta rejects a field, adjust the configuration — do not guess a
different API. No other Meta endpoint is called from this codebase.
"""

import json
import os
import threading
import urllib.error
import urllib.request

from .scrubber import scrub_before_write

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_MAX_CALLS = 5
# Reasoning tokens count against max_tokens. Verified live 2026-11-01:
# Muse Spark spent 254 reasoning tokens on a trivial prompt and hit
# finish_reason "length" with content None at max_tokens=256, leaving
# no room for the visible answer. 1024 leaves room for reasoning
# plus the short JSON/shorthand reply.
DEFAULT_MAX_TOKENS = 1024

PILLARS = [
    "computing-in-memory", "event-driven spiking",
    "extreme sparsity / dynamic routing",
    "continuous local learning", "accessibility", "security",
]
_VERDICTS = ("consistent", "conflicting", "rejected")

# Process-wide live-call counter: the budget is per process, not per
# client instance, so a second client cannot restart the count.
_process_calls = 0
_process_lock = threading.Lock()


def reset_live_call_budget():
    """Reset the process-wide live-call counter. Test-only helper.

    Production code never calls this; it exists so mocked-HTTP tests
    in one process do not consume each other's budget.
    """
    global _process_calls
    with _process_lock:
        _process_calls = 0


class LiveMetaClient:
    """Real Meta Model API client. Same verify()/compress() shapes as
    the fake client, with ``live: True``. ``call_count`` counts live
    attempts only; scrub refusals and budget refusals do not count.
    """

    def __init__(self, model=None, base_url=None, max_calls=None):
        # Environment only. No file is ever read for a credential.
        self.api_key = os.environ.get("META_API_KEY") or ""
        self.model = model or os.environ.get("HIVE_MIND_META_MODEL") or DEFAULT_MODEL
        self.base_url = (
            base_url or os.environ.get("HIVE_MIND_META_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.max_calls = self._resolve_max_calls(max_calls)
        self.call_count = 0
        # Audit trail only: method/model/live. Payloads and the key
        # are never recorded here.
        self.calls = []

    @staticmethod
    def _resolve_max_calls(requested):
        raw = requested
        if raw is None:
            raw = os.environ.get("HIVE_MIND_LIVE_MAX_CALLS")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_MAX_CALLS
        if value <= 0:
            return DEFAULT_MAX_CALLS
        if value <= DEFAULT_MAX_CALLS:
            return value
        # Raising past 5 requires the explicit unsafe override.
        if os.environ.get("HIVE_MIND_LIVE_UNSAFE_RAISE_BUDGET") == "1":
            return value
        return DEFAULT_MAX_CALLS

    # -- error helpers ---------------------------------------------------

    def _missing_key_error(self):
        return {
            "model": self.model,
            "live": True,
            "error": "META_API_KEY is not set in the environment; "
                     "no live call was attempted",
        }

    def _budget_error(self):
        return {
            "model": self.model,
            "live": True,
            "error": f"live call budget reached ({self.max_calls} calls "
                     "per process); no live call was attempted",
        }

    def _scrub_error(self, trapped_count):
        return {
            "model": self.model,
            "live": True,
            "error": "scrubber trapped a secret in the payload; "
                     "the call was refused before any network request",
            "trapped_count": trapped_count,
        }

    # -- HTTP ------------------------------------------------------------

    def _post_chat(self, messages, max_tokens):
        """One POST, no retries. Returns (content_str, error_dict|None).

        The caller has already passed the scrub and budget checks.
        ``content_str`` is the assistant message text, or "" on error.
        """
        global _process_calls
        with _process_lock:
            if _process_calls >= self.max_calls:
                return "", self._budget_error()
            _process_calls += 1
        self.call_count += 1
        self.calls.append({"method": "chat", "model": self.model, "live": True})
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            response = urllib.request.urlopen(request, timeout=30)
            try:
                raw = response.read()
            finally:
                try:
                    response.close()
                except Exception:
                    pass
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:200]
            except Exception:
                detail = ""
            return "", {
                "model": self.model,
                "live": True,
                "error": f"Meta API HTTP {exc.code}: {detail}".strip(),
            }
        except urllib.error.URLError as exc:
            return "", {
                "model": self.model,
                "live": True,
                "error": f"Meta API request failed: {exc.reason}",
            }
        except Exception as exc:  # network/transport failure, no retry
            return "", {
                "model": self.model,
                "live": True,
                "error": f"Meta API request failed: {type(exc).__name__}",
            }
        try:
            payload = json.loads(raw.decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            return "", {
                "model": self.model,
                "live": True,
                "error": "Meta API response was not a chat-completion "
                         "payload; no verification was performed",
            }
        if not isinstance(content, str) or not content.strip():
            return "", {
                "model": self.model,
                "live": True,
                "error": "Meta API returned an empty message; "
                         "no verification was performed",
            }
        return content, None

    # -- fake-compatible interface ----------------------------------------

    def verify(self, candidate_fact, domain_repo):
        """Pillar-check one fact with the live model.

        Returns the fake client's shape plus ``live: True`` and a
        ``reason``. On any refusal or failure the dict carries
        ``verdict: "error"`` and an ``"error"`` message.
        """
        if not self.api_key:
            return {**self._missing_key_error(),
                    "verdict": "error", "pillar_failures": []}
        scrubbed = scrub_before_write(candidate_fact, "standard")
        if scrubbed["trapped_count"] > 0:
            return {**self._scrub_error(scrubbed["trapped_count"]),
                    "verdict": "error", "pillar_failures": []}
        fact = scrubbed["scrubbed_text"]
        messages = [
            {
                "role": "system",
                "content": (
                    "You check one candidate fact against six pillars: "
                    "computing-in-memory, event-driven spiking, extreme "
                    "sparsity / dynamic routing, continuous local learning, "
                    "accessibility, security. Return ONLY a JSON object: "
                    '{"verdict": "consistent" | "conflicting" | "rejected", '
                    '"pillar_failures": ["<pillar name>", ...], '
                    '"reason": "<one sentence>"}. '
                    "Reject a fact that would leak a secret or cause harm. "
                    "Flag conflicting when it contradicts the stated domain "
                    "context. Otherwise consistent."
                ),
            },
            {
                "role": "user",
                "content": f"Domain: {domain_repo}\nCandidate fact: {fact}",
            },
        ]
        content, error = self._post_chat(messages, max_tokens=DEFAULT_MAX_TOKENS)
        if error is not None:
            return {**error, "verdict": "error", "pillar_failures": []}
        stripped = content.strip()
        for fence in ("```json", "```"):
            if stripped.startswith(fence):
                stripped = stripped[len(fence):].strip()
            if stripped.endswith("```"):
                stripped = stripped[:-3].strip()
        try:
            parsed = json.loads(stripped)
        except ValueError:
            return {
                "model": self.model,
                "live": True,
                "verdict": "error",
                "pillar_failures": [],
                "error": "model response was not parseable JSON; "
                         "no verification was performed",
            }
        if not isinstance(parsed, dict) or parsed.get("verdict") not in _VERDICTS:
            return {
                "model": self.model,
                "live": True,
                "verdict": "error",
                "pillar_failures": [],
                "error": "model response did not contain a valid verdict; "
                         "no verification was performed",
            }
        failures = parsed.get("pillar_failures") or []
        failures = [f for f in failures if isinstance(f, str)]
        return {
            "model": self.model,
            "live": True,
            "verdict": parsed["verdict"],
            "pillar_failures": failures,
            "pillars_checked": list(PILLARS),
            "reason": str(parsed.get("reason") or ""),
        }

    def compress(self, text):
        """Compress text to Caveman shorthand with the live model.

        Returns the fake client's shape: ``model``, ``live``, and
        ``compressed``. On refusal or failure ``compressed`` is ""
        and the dict carries an ``"error"`` message.
        """
        if not self.api_key:
            return {**self._missing_key_error(), "compressed": ""}
        scrubbed = scrub_before_write(text, "standard")
        if scrubbed["trapped_count"] > 0:
            return {**self._scrub_error(scrubbed["trapped_count"]),
                    "compressed": ""}
        messages = [
            {
                "role": "system",
                "content": (
                    "Compress the text into Caveman shorthand: keep "
                    "entities, numbers, dates, and content words; drop "
                    "filler words. Never invent facts. Return only the "
                    "shorthand, no explanation."
                ),
            },
            {"role": "user", "content": scrubbed["scrubbed_text"]},
        ]
        content, error = self._post_chat(messages, max_tokens=DEFAULT_MAX_TOKENS)
        if error is not None:
            return {**error, "compressed": ""}
        return {
            "model": self.model,
            "live": True,
            "compressed": content.strip(),
        }
