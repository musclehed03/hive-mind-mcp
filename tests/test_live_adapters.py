"""Live-adapter tests: mocked HTTP only. Zero network, zero real keys.

The live clients in app/live_meta.py and app/live_supabase.py are
real HTTP clients, but these tests never let them touch a network:
every ``urlopen`` call is mocked, and every credential is an
obviously-fake value (``LLM_fake-test``). The default path stays
fake — see the factory tests — and a live call without a key, over
budget, or refused by the scrubber must never attempt a request.
"""

import hashlib
import json
import urllib.error
import urllib.request
from unittest import mock

import pytest

from app.crosshatch import crosshatch_verify
from app.dispatch import dispatch_tool
from app.fake_meta import FakeMetaClient
from app.live_clients import get_meta_client, get_snapshot_adapter, live_enabled
from app.live_meta import LiveMetaClient, reset_live_call_budget
from app.live_supabase import LiveSupabaseBucketAdapter, LiveSupabaseError
from app.store import Store

FAKE_KEY = "LLM_fake-test"
FAKE_SUPABASE_URL = "https://example.test"
FAKE_SERVICE_KEY = "fake-service-key"

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


@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "v.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


class _Resp:
    """Minimal urlopen stand-in: status + read() + close()."""

    def __init__(self, body=b"", status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def close(self):
        pass


def _chat_body(verdict="consistent", failures=None):
    payload = {
        "choices": [{
            "message": {"content": json.dumps({
                "verdict": verdict,
                "pillar_failures": failures or [],
                "reason": "mocked",
            })},
        }],
    }
    return json.dumps(payload).encode("utf-8")


def _headers_of(request):
    return {k.lower(): v for k, v in request.header_items()}


def _http_error(url, code, msg="error"):
    return urllib.error.HTTPError(url, code, msg, {}, None)


# -- factory: default is always fake --------------------------------------

def test_factory_default_is_fake(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    monkeypatch.setenv("SUPABASE_URL", FAKE_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SERVICE_KEY)
    assert live_enabled() is False
    assert isinstance(get_meta_client(), FakeMetaClient)
    assert get_snapshot_adapter("supabase") is None


def test_factory_live_zero_is_fake(monkeypatch):
    monkeypatch.setenv("HIVE_MIND_LIVE", "0")
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    assert isinstance(get_meta_client(), FakeMetaClient)


def test_factory_live_returns_live_meta_and_supabase(monkeypatch):
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    monkeypatch.setenv("SUPABASE_URL", FAKE_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SERVICE_KEY)
    assert isinstance(get_meta_client(), LiveMetaClient)
    adapter = get_snapshot_adapter("supabase")
    assert isinstance(adapter, LiveSupabaseBucketAdapter)
    assert get_snapshot_adapter("drive") is None


def test_factory_supabase_without_credentials_is_none(monkeypatch):
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    assert get_snapshot_adapter("supabase") is None


# -- live Meta: missing key, no network -----------------------------------

def test_live_verify_without_key_makes_no_request(monkeypatch):
    with mock.patch.object(urllib.request, "urlopen") as mock_open:
        result = LiveMetaClient().verify("A plain fact", "coding")
    assert result["verdict"] == "error"
    assert result["live"] is True
    assert "META_API_KEY" in result["error"]
    assert FAKE_KEY not in str(result)
    mock_open.assert_not_called()


def test_live_compress_without_key_makes_no_request():
    with mock.patch.object(urllib.request, "urlopen") as mock_open:
        result = LiveMetaClient().compress("some text to compress")
    assert result["compressed"] == ""
    assert "error" in result
    mock_open.assert_not_called()


def test_live_flag_without_key_errors_via_factory(monkeypatch):
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    client = get_meta_client()
    with mock.patch.object(urllib.request, "urlopen") as mock_open:
        result = client.verify("A plain fact", "coding")
    assert result["verdict"] == "error"
    mock_open.assert_not_called()


# -- live Meta: mocked HTTP, request shape --------------------------------

def test_live_verify_request_shape_and_success(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        result = LiveMetaClient().verify("The shop opens at 9am", "general")
    assert result["verdict"] == "consistent"
    assert result["live"] is True
    assert result["model"] == "muse-spark-1.3"
    assert result["pillar_failures"] == []
    request = mock_open.call_args[0][0]
    assert request.full_url == "https://api.meta.ai/v1/chat/completions"
    assert request.get_method() == "POST"
    headers = _headers_of(request)
    assert headers["authorization"].startswith("Bearer ")
    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == "muse-spark-1.3"
    assert body["messages"][0]["role"] == "system"
    assert "The shop opens at 9am" in body["messages"][1]["content"]
    # The key appears only in the header, never in the body.
    assert FAKE_KEY.encode() not in request.data


def test_live_model_and_base_url_are_configurable(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    monkeypatch.setenv("HIVE_MIND_META_MODEL", "muse-spark-9.9")
    monkeypatch.setenv("HIVE_MIND_META_BASE_URL", "https://example.test/v1")
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        result = LiveMetaClient().verify("A fact", "coding")
    assert result["model"] == "muse-spark-9.9"
    request = mock_open.call_args[0][0]
    assert request.full_url == "https://example.test/v1/chat/completions"


def test_live_compress_returns_model_text(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    body = json.dumps({"choices": [{"message": {"content": "SHOP 9AM SAT"}}]}).encode()
    with mock.patch.object(urllib.request, "urlopen", return_value=_Resp(body)):
        result = LiveMetaClient().compress("The shop opens at 9am on Saturdays")
    assert result == {"model": "muse-spark-1.3", "live": True,
                      "compressed": "SHOP 9AM SAT"}


def test_live_verify_unparseable_response_is_error_not_success(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    body = json.dumps({"choices": [{"message": {"content": "just some prose"}}]}).encode()
    with mock.patch.object(urllib.request, "urlopen", return_value=_Resp(body)):
        result = LiveMetaClient().verify("A fact", "coding")
    assert result["verdict"] == "error"
    assert "error" in result


def test_live_verify_http_error_is_error_dict(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen",
        side_effect=_http_error("https://example.test", 429, "Too Many Requests"),
    ):
        result = LiveMetaClient().verify("A fact", "coding")
    assert result["verdict"] == "error"
    assert "429" in result["error"]
    assert FAKE_KEY not in result["error"]


# -- budget ----------------------------------------------------------------

def test_live_budget_cap_enforced_at_five(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    client = LiveMetaClient()
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        for _ in range(5):
            result = client.verify("A fact", "coding")
            assert result["verdict"] == "consistent"
        refused = client.verify("One more fact", "coding")
    assert refused["verdict"] == "error"
    assert "budget" in refused["error"]
    assert mock_open.call_count == 5
    assert client.call_count == 5


def test_live_budget_can_be_lowered_not_raised(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    monkeypatch.setenv("HIVE_MIND_LIVE_MAX_CALLS", "2")
    assert LiveMetaClient().max_calls == 2
    monkeypatch.setenv("HIVE_MIND_LIVE_MAX_CALLS", "10")
    assert LiveMetaClient().max_calls == 5
    monkeypatch.setenv("HIVE_MIND_LIVE_UNSAFE_RAISE_BUDGET", "1")
    assert LiveMetaClient().max_calls == 10


def test_live_budget_lowered_to_two_blocks_third_call(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    client = LiveMetaClient(max_calls=2)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        assert client.verify("Fact one", "coding")["verdict"] == "consistent"
        assert client.verify("Fact two", "coding")["verdict"] == "consistent"
        assert client.verify("Fact three", "coding")["verdict"] == "error"
    assert mock_open.call_count == 2


# -- scrubber refusal -------------------------------------------------------

def test_live_verify_scrub_refusal_blocks_send(monkeypatch):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    client = LiveMetaClient()
    leaked = "the leaked key is LLM_fake-secret123 do not send it"
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ) as mock_open:
        refused = client.verify(leaked, "coding")
        assert refused["verdict"] == "error"
        assert "scrubber" in refused["error"]
        assert "LLM_fake-secret123" not in str(refused)
        mock_open.assert_not_called()
        assert client.call_count == 0
        # A clean fact after a refusal still works: no budget consumed.
        assert client.verify("A clean fact", "coding")["verdict"] == "consistent"
    assert mock_open.call_count == 1


# -- live Supabase: request shapes -------------------------------------------

def _supabase_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", FAKE_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SERVICE_KEY)
    return LiveSupabaseBucketAdapter()


def test_supabase_upload_request_shape(monkeypatch):
    adapter = _supabase_env(monkeypatch)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(b"", 200)
    ) as mock_open:
        adapter.upload("hive-mind-snapshots/test.zip", b"bundle-bytes")
    request = mock_open.call_args[0][0]
    assert request.get_method() == "POST"
    assert request.full_url == (
        "https://example.test/storage/v1/object/hive-mind-snapshots/test.zip"
    )
    assert request.data == b"bundle-bytes"
    headers = _headers_of(request)
    assert "apikey" in headers
    assert headers["authorization"].startswith("Bearer ")
    assert headers["x-upsert"] == "true"
    assert adapter.upload_count == 1


def test_supabase_download_and_sha256(monkeypatch):
    adapter = _supabase_env(monkeypatch)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(b"abc", 200)
    ) as mock_open:
        assert adapter.download("test.zip") == b"abc"
        assert adapter.sha256("test.zip") == hashlib.sha256(b"abc").hexdigest()
    for call in mock_open.call_args_list:
        assert call[0][0].get_method() == "GET"
    assert adapter.download_count == 2


def test_supabase_exists_head(monkeypatch):
    adapter = _supabase_env(monkeypatch)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(b"", 200)
    ) as mock_open:
        assert adapter.exists("test.zip") is True
    assert mock_open.call_args[0][0].get_method() == "HEAD"
    with mock.patch.object(
        urllib.request, "urlopen",
        side_effect=_http_error("https://example.test", 404, "Not Found"),
    ):
        assert adapter.exists("missing.zip") is False


def test_supabase_delete_request_shape(monkeypatch):
    adapter = _supabase_env(monkeypatch)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(b"", 200)
    ) as mock_open:
        adapter.delete("hive-mind-snapshots/test.zip")
    request = mock_open.call_args[0][0]
    assert request.get_method() == "DELETE"
    assert request.full_url == "https://example.test/storage/v1/object/hive-mind-snapshots"
    assert json.loads(request.data.decode("utf-8")) == {"prefixes": ["test.zip"]}


def test_supabase_upload_http_failure_raises_clear_error(monkeypatch):
    adapter = _supabase_env(monkeypatch)
    with mock.patch.object(
        urllib.request, "urlopen",
        side_effect=_http_error("https://example.test", 500, "Server Error"),
    ):
        with pytest.raises(LiveSupabaseError) as excinfo:
            adapter.upload("test.zip", b"data")
    assert "500" in str(excinfo.value)
    assert FAKE_SERVICE_KEY not in str(excinfo.value)
    assert adapter.upload_count == 0


def test_supabase_without_credentials_makes_no_request():
    adapter = LiveSupabaseBucketAdapter()
    with mock.patch.object(urllib.request, "urlopen") as mock_open:
        with pytest.raises(LiveSupabaseError) as excinfo:
            adapter.upload("test.zip", b"data")
    assert "SUPABASE_URL" in str(excinfo.value)
    mock_open.assert_not_called()


# -- drop-in wiring: cross-hatch + dispatch ----------------------------------

def test_crosshatch_with_live_client_success(monkeypatch, store):
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ):
        result = crosshatch_verify(
            "The shop opens at 9am on Saturdays", "general", "notes", "",
            store, meta_client=LiveMetaClient(),
        )
    assert result["status"] == "verified"
    assert result["live"] is True
    assert "live" in result["provenance"]["generated_by"]
    assert result["provenance"]["model"] == "muse-spark-1.3"
    assert store.memory_stats()["total"] == 1


def test_crosshatch_with_live_client_error_stores_nothing(store):
    result = crosshatch_verify(
        "A fact", "general", "notes", "", store,
        meta_client=LiveMetaClient(),
    )
    assert result["status"] == "error"
    assert "META_API_KEY" in result["error"]
    assert store.memory_stats()["total"] == 0


def test_dispatch_uses_fake_by_default_and_live_when_flagged(monkeypatch, store):
    payload, err = dispatch_tool("hivemind_crosshatch_verify", {
        "candidate_fact": "The library opens at 10am", "domain_repo": "general",
        "source_citation": "notes", "supersede_id": ""}, store=store)
    assert err is False and payload["status"] == "verified"
    assert payload["live"] is False

    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("META_API_KEY", FAKE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen", return_value=_Resp(_chat_body())
    ):
        payload, err = dispatch_tool("hivemind_crosshatch_verify", {
            "candidate_fact": "The garden grows tomatoes in summer",
            "domain_repo": "general",
            "source_citation": "notes", "supersede_id": ""}, store=store)
    assert err is False and payload["status"] == "verified"
    assert payload["live"] is True


def test_dispatch_snapshot_live_upload_and_delete(monkeypatch, store):
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("SUPABASE_URL", FAKE_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SERVICE_KEY)
    captured = {}

    def _handler(request, timeout=30):
        method = request.get_method()
        if method == "POST":
            captured["uploaded"] = request.data
            return _Resp(b"", 200)
        if method == "GET":
            return _Resp(captured["uploaded"], 200)
        if method == "DELETE":
            captured["delete_body"] = request.data
            return _Resp(b"", 200)
        raise AssertionError(method)

    with mock.patch.object(urllib.request, "urlopen", side_effect=_handler):
        payload, err = dispatch_tool("hivemind_snapshot_backup", {
            "destination_target": "supabase", "schedule_interval": "now",
            "user_handshake_token": "yes"}, store=store)
    assert err is False
    assert payload["status"] == "ok"
    assert payload["backed_up"] is True
    assert payload["verified_callback"] is True
    with mock.patch.object(urllib.request, "urlopen", side_effect=_handler):
        get_snapshot_adapter("supabase").delete(payload["storage_path"])
    assert json.loads(captured["delete_body"].decode("utf-8"))["prefixes"] == [
        payload["storage_path"].split("hive-mind-snapshots/", 1)[1]
    ]


def test_dispatch_snapshot_http_failure_is_error_payload(monkeypatch, store):
    monkeypatch.setenv("HIVE_MIND_LIVE", "1")
    monkeypatch.setenv("SUPABASE_URL", FAKE_SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SERVICE_KEY)
    with mock.patch.object(
        urllib.request, "urlopen",
        side_effect=_http_error("https://example.test", 500, "Server Error"),
    ):
        payload, err = dispatch_tool("hivemind_snapshot_backup", {
            "destination_target": "supabase", "schedule_interval": "now",
            "user_handshake_token": "yes"}, store=store)
    assert err is True
    assert payload["status"] == "error"
    assert payload["backed_up"] is False
    assert "500" in payload["error"]
