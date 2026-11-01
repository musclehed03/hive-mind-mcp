"""Block 15: loopback base URLs need no API key; remote ones still do.

Mocked HTTP only. Zero network, zero real keys. The fake key below
is a test-only placeholder string, never a credential.
"""

import json
import urllib.error
import urllib.request

import pytest
from unittest import mock

from app.live_meta import LiveMetaClient, reset_live_call_budget

FAKE_KEY = "test-only-fake-key"

_ENV_VARS = (
    "HIVE_MIND_LIVE", "META_API_KEY", "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY", "HIVE_MIND_LIVE_MAX_CALLS",
    "HIVE_MIND_LIVE_UNSAFE_RAISE_BUDGET", "HIVE_MIND_META_MODEL",
    "HIVE_MIND_META_BASE_URL", "HIVE_MIND_SUPABASE_BUCKET",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    reset_live_call_budget()
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield
    reset_live_call_budget()


class _Resp:
    """Minimal urlopen stand-in: read() + close()."""

    def __init__(self, body=b""):
        self._body = body

    def read(self):
        return self._body

    def close(self):
        pass


def _chat_body(verdict="consistent"):
    payload = {
        "choices": [{
            "message": {"content": json.dumps({
                "verdict": verdict,
                "pillar_failures": [],
                "reason": "mocked",
            })},
        }],
    }
    return json.dumps(payload).encode("utf-8")


def _headers_of(request):
    return {k.lower(): v for k, v in request.header_items()}


def _client(monkeypatch, base_url, key=None):
    if base_url is not None:
        monkeypatch.setenv("HIVE_MIND_META_BASE_URL", base_url)
    if key is not None:
        monkeypatch.setenv("META_API_KEY", key)
    return LiveMetaClient()


# -- loopback: no key, request attempted, no auth header --------------

@pytest.mark.parametrize("base_url", [
    "http://localhost:11434/v1",
    "https://localhost:8080/v1",
    "http://127.0.0.1:8080/api/v1",
    "http://127.5.6.7:11434/v1",
    "http://[::1]:11434/v1",
])
def test_loopback_without_key_attempts_request_without_auth(
        monkeypatch, base_url):
    client = _client(monkeypatch, base_url)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        result = client.verify("The shop opens at 9am on Saturdays",
                               "test-domain")
    assert result["verdict"] == "consistent"
    assert "error" not in result
    mock_open.assert_called_once()
    request = mock_open.call_args[0][0]
    assert request.full_url == base_url + "/chat/completions"
    assert "authorization" not in _headers_of(request)


def test_loopback_without_key_compress_attempts_request(monkeypatch):
    client = _client(monkeypatch, "http://localhost:11434/v1")
    body = json.dumps({"choices": [{"message": {
        "content": "shop opens 9am Sat"}}]}).encode("utf-8")
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(body)
    ) as mock_open:
        result = client.compress("The shop opens at 9am on Saturdays.")
    assert result["compressed"] == "shop opens 9am Sat"
    assert "error" not in result
    mock_open.assert_called_once()
    assert "authorization" not in _headers_of(mock_open.call_args[0][0])


# -- remote: no key, refused, no network attempt ------------------------

@pytest.mark.parametrize("base_url", [
    None,  # default Meta base
    "https://openrouter.ai/api/v1",
    "https://api.example.test/v1",
])
def test_remote_without_key_refused_without_network(monkeypatch, base_url):
    client = _client(monkeypatch, base_url)
    with mock.patch.object(urllib.request, "urlopen") as mock_open:
        result = client.verify("The shop opens at 9am on Saturdays",
                               "test-domain")
        compress = client.compress("The shop opens at 9am on Saturdays.")
    assert result["verdict"] == "error"
    assert "META_API_KEY" in result["error"]
    assert compress["compressed"] == ""
    assert "META_API_KEY" in compress["error"]
    mock_open.assert_not_called()


@pytest.mark.parametrize("base_url", [
    "https://localhost.example.com/v1",
    "https://127.0.0.1.example.com/v1",
    "https://notlocalhost/v1",
])
def test_lookalike_hostnames_are_not_loopback(monkeypatch, base_url):
    client = _client(monkeypatch, base_url)
    with mock.patch.object(urllib.request, "urlopen") as mock_open:
        result = client.verify("The shop opens at 9am on Saturdays",
                               "test-domain")
    assert result["verdict"] == "error"
    assert "META_API_KEY" in result["error"]
    mock_open.assert_not_called()


# -- loopback with a key: key still sent (backwards compatible) --------

def test_loopback_with_key_still_sends_authorization(monkeypatch):
    client = _client(monkeypatch, "http://localhost:11434/v1", key=FAKE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        result = client.verify("The shop opens at 9am on Saturdays",
                               "test-domain")
    assert result["verdict"] == "consistent"
    headers = _headers_of(mock_open.call_args[0][0])
    assert headers["authorization"] == "Bearer " + FAKE_KEY


def test_remote_with_key_sends_authorization_unchanged(monkeypatch):
    client = _client(monkeypatch, "https://openrouter.ai/api/v1",
                     key=FAKE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        result = client.verify("The shop opens at 9am on Saturdays",
                               "test-domain")
    assert result["verdict"] == "consistent"
    headers = _headers_of(mock_open.call_args[0][0])
    assert headers["authorization"] == "Bearer " + FAKE_KEY
