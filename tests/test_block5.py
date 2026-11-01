"""Block 5 gate tests: snapshot backup (fake adapters only)."""

import hashlib
import io
import json
import os
import zipfile

import pytest

from app.dispatch import dispatch_tool
from app.fake_supabase import (
    FakeBucketAdapter,
    FakeUploadError,
    fake_drive_adapter,
    fake_supabase_adapter,
)
from app.snapshot import build_bundle, snapshot_backup
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
