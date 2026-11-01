"""Block 5 gate tests: snapshot backup (fake adapters only)."""

import hashlib
import io
import json
import os
import uuid
import zipfile

import pytest

from app.dispatch import dispatch_tool
from app.fake_supabase import (
    FakeBucketAdapter,
    FakeUploadError,
    fake_drive_adapter,
    fake_supabase_adapter,
)
from app.scrubber import contains_secret
from app.snapshot import (
    _bundle_text_for_scrub_gate,
    build_bundle,
    snapshot_backup,
)
from app.store import Store


@pytest.fixture()
def store(tmp_path):
    s = Store(db_path=str(tmp_path / "s.db"), vault_dir=str(tmp_path / "vault"))
    yield s
    s.close()


def _snap(store, dest="supabase", schedule="7d", token="user-yes", adapter=None):
    return snapshot_backup(dest, schedule, token, store, adapter=adapter)


def test_bundle_is_inspectable_zip_with_manifest(store):
    store.remember("The shop opens at 9am", domain="general")
    bundle, manifest = build_bundle(store)
    assert manifest["memory_count"] == 1
    with zipfile.ZipFile(io.BytesIO(bundle)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "vault/memories.jsonl" in names
        assert "hive-mind.db" in names
        assert "The shop opens at 9am" in zf.read("vault/memories.jsonl").decode()


def test_fake_adapter_upload_and_verified_callback(store):
    store.remember("Backup me please", domain="general")
    adapter = fake_supabase_adapter()
    result = _snap(store, adapter=adapter)
    assert result["status"] == "ok"
    assert result["backed_up"] is True
    assert result["verified_callback"] is True
    assert adapter.upload_count == 1
    assert adapter.download_count == 1
    assert adapter.sha256(result["storage_path"]) == result["sha256"]
    assert result["sha256"] == hashlib.sha256(
        adapter.download(result["storage_path"])).hexdigest()


def _find_gate_tripping_id():
    """A random uuid4 hex whose JSONL line trips the scrub gate.

    A 32-hex-char id ending in a long digit run matches the standard
    PHONE pattern, so a small fraction of random ids trip
    ``contains_secret`` at "standard" when the whole JSONL line is
    scanned. Search until one is found (a few hundred draws on
    average); the cap keeps the test bounded.
    """
    for _ in range(5000):
        candidate = uuid.uuid4().hex
        line = json.dumps({
            "event": "remember", "id": candidate,
            "text": "Backup me please", "entities": [], "source": "",
            "domain": "general", "status": "active",
            "created_at": "2026-11-01T00:00:00+00:00", "provenance": {},
        }, sort_keys=True)
        if contains_secret(line, "standard"):
            return candidate
    raise AssertionError("no gate-tripping id found in 5000 random uuids")


def test_scrub_gate_scans_fact_text_only(store):
    # Real bundle: no id or timestamp may reach the gate.
    store.remember("Backup me please", domain="general")
    bundle, _ = build_bundle(store)
    gate_text = _bundle_text_for_scrub_gate(bundle)
    assert "Backup me please" in gate_text
    for mem in store.list_memories(limit=10000):
        assert mem["id"] not in gate_text
        assert mem["created_at"] not in gate_text
    assert contains_secret(gate_text, "standard") is False

    # Synthetic bundle: a gate-tripping id in the JSONL "id" field and
    # in the note frontmatter must not trip the gate, an unparseable
    # line must not crash it, and a secret in the fact text must trip.
    tripping = _find_gate_tripping_id()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("vault/memories.jsonl", json.dumps({
            "event": "remember", "id": tripping,
            "text": "Backup me please", "entities": [], "source": "",
            "domain": "general", "status": "active",
            "created_at": "2026-11-01T00:00:00+00:00", "provenance": {},
        }, sort_keys=True) + "\nnot json {oops\n")
        zf.writestr(f"vault/memories/{tripping}.md",
                    f"---\nid: {tripping}\nsource: \ndomain: general\n"
                    "created: 2026-11-01T00:00:00+00:00\n---\n\n"
                    "Backup me please\n")
    gate_text = _bundle_text_for_scrub_gate(buf.getvalue())
    assert tripping not in gate_text
    assert "Backup me please" in gate_text
    assert contains_secret(gate_text, "standard") is False

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("vault/memories.jsonl", json.dumps({
            "text": "contact test@example.com about the demo",
        }) + "\n")
    assert contains_secret(
        _bundle_text_for_scrub_gate(buf.getvalue()), "standard") is True


def test_snapshot_with_gate_tripping_memory_id_still_backs_up(store):
    # Regression: a memory whose system-generated id would trip the
    # gate if scanned whole must still back up. Store.remember()
    # generates its own id, so rewrite the vault mirror to carry the
    # tripping id, as if remember() had generated it; the gate reads
    # the vault mirror, not the SQLite row.
    tripping = _find_gate_tripping_id()
    store.remember("Backup me please", domain="general")
    jsonl_path = os.path.join(store.vault_dir, "memories.jsonl")
    with open(jsonl_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    for record in records:
        record["id"] = tripping
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    notes_dir = os.path.join(store.vault_dir, "memories")
    for fname in os.listdir(notes_dir):
        if not fname.endswith(".md"):
            continue
        note_path = os.path.join(notes_dir, fname)
        with open(note_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        lines = [f"id: {tripping}" if line.startswith("id: ") else line
                 for line in lines]
        new_path = os.path.join(notes_dir, f"{tripping}.md")
        with open(new_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        if new_path != note_path:
            os.remove(note_path)
    adapter = fake_supabase_adapter()
    result = _snap(store, adapter=adapter)
    assert result["status"] == "ok"
    assert result["backed_up"] is True
    assert result["verified_callback"] is True
    assert adapter.upload_count == 1


def test_upload_failure_never_reported_backed_up_and_local_kept(store):
    store.remember("Backup me please", domain="general")
    adapter = fake_supabase_adapter()
    adapter.fail_next_upload = True
    result = _snap(store, adapter=adapter)
    assert result["status"] == "error"
    assert result["backed_up"] is False
    assert result["verified_callback"] is False
    assert os.path.exists(result["local_bundle_path"])


def test_hash_mismatch_never_reported_backed_up(store):
    class CorruptAdapter(FakeBucketAdapter):
        def download(self, path):
            return b"corrupted-bytes"

    store.remember("Backup me please", domain="general")
    result = _snap(store, adapter=CorruptAdapter("corrupt"))
    assert result["status"] == "error"
    assert result["backed_up"] is False
    assert "hash" in result["error"]


def test_snapshot_with_secret_refused_before_upload(store):
    # Direct store write bypassing capture (defence in depth): the
    # scrub gate must still refuse the bundle.
    store.remember("contact test@example.com about the demo")
    adapter = fake_supabase_adapter()
    result = _snap(store, adapter=adapter)
    assert result["status"] == "error"
    assert adapter.upload_count == 0
    assert "scrub gate" in result["error"]


def test_local_only_mode_without_adapter(store):
    store.remember("Local snapshot please", domain="general")
    result = _snap(store, dest="drive", adapter=None)
    assert result["status"] == "local_only"
    assert result["backed_up"] is False
    assert result["verified_callback"] is True
    assert os.path.exists(result["storage_path"])
    assert "UNVERIFIED" in result["note"]


def test_snapshot_requires_handshake_and_valid_args(store):
    with pytest.raises(ValueError):
        _snap(store, token="")
    with pytest.raises(ValueError):
        _snap(store, dest="carrier-pigeon")
    with pytest.raises(ValueError):
        _snap(store, schedule="fortnightly")
    drive = _snap(store, dest="drive", schedule="now", adapter=fake_drive_adapter())
    assert drive["status"] == "ok"
    assert drive["schedule_interval"] == "now"


def test_snapshot_via_dispatch_is_local_only(store):
    store.remember("Dispatch snapshot please", domain="general")
    payload, err = dispatch_tool("hivemind_snapshot_backup", {
        "destination_target": "supabase", "schedule_interval": "7d",
        "user_handshake_token": "yes"}, store=store)
    assert err is False
    assert payload["status"] == "local_only"
    assert payload["verified_callback"] is True
