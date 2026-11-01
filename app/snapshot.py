"""Block 5 — Snapshot backup (local bundle + verified callback).

The bundle is an inspectable ZIP: a copy of the SQLite database, the
JSONL vault mirror, and the Markdown notes, plus a manifest with a
SHA-256 per file and the memory count. Before any upload, the bundle
text is run through the Block 2 scrubber gate: a bundle containing a
secret is REFUSED and never uploaded.

Success is reported only after the verified callback: the uploaded
object is downloaded again and its SHA-256 is compared with the
local bundle's. A mismatch, an upload failure, or a download failure
is an error — never reported as backed up — and the local bundle is
kept so nothing is lost.

With no adapter supplied, the tool runs local-only: it writes and
verifies the bundle under the vault and reports status "local_only".
That is the default in this codebase, because no live Supabase/Drive
credentials exist here. The live upload gate is UNVERIFIED.
"""

import hashlib
import io
import json
import os
import sqlite3
import zipfile
from datetime import datetime, timezone

from .scrubber import contains_secret

SCHEDULES = ("7d", "1d", "30d", "now")
DESTINATIONS = ("supabase", "drive")


def _db_copy_bytes(store):
    """A consistent copy of the SQLite file via the backup API.

    The backup API copies the file itself (including the sqlite-vec
    virtual table, which iterdump cannot dump). The bundle stores the
    copy as ``hive-mind.db``; the ``.sql`` name in earlier drafts was
    wrong for a binary copy and is not used.
    """
    import tempfile

    source = sqlite3.connect(store.db_path)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    try:
        target = sqlite3.connect(tmp.name)
        try:
            source.backup(target)
        finally:
            target.close()
        with open(tmp.name, "rb") as f:
            return f.read()
    finally:
        source.close()
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def build_bundle(store):
    """Build the snapshot ZIP bytes + manifest. No network, no upload."""
    memories = store.list_memories(limit=10000)
    db_bytes = _db_copy_bytes(store)
    jsonl_path = os.path.join(store.vault_dir, "memories.jsonl")
    jsonl_bytes = b""
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "rb") as f:
            jsonl_bytes = f.read()
    notes = {}
    notes_dir = os.path.join(store.vault_dir, "memories")
    if os.path.isdir(notes_dir):
        for fname in sorted(os.listdir(notes_dir)):
            if fname.endswith(".md"):
                with open(os.path.join(notes_dir, fname), "rb") as f:
                    notes[f"vault/memories/{fname}"] = f.read()
    files = {
        "hive-mind.db": db_bytes,
        "vault/memories.jsonl": jsonl_bytes,
    }
    files.update(notes)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "memory_count": len(memories),
        "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in files.items()
        },
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    bundle = buf.getvalue()
    return bundle, manifest


def _bundle_text_for_scrub_gate(bundle):
    """Decoded fact text for the scrub gate (binary + manifest excluded).

    Only the JSONL mirror and Markdown notes are scanned: the manifest
    holds SHA-256 hashes, which are hashes, not secrets, and must not
    trip the entropy pass. The gate runs at "standard" strictness for
    the same reason — the entropy pass is for untrusted input text,
    not for the bundle's own hashes and ids.
    """
    buf = io.BytesIO(bundle)
    chunks = []
    with zipfile.ZipFile(buf) as zf:
        for name in zf.namelist():
            if name.endswith((".jsonl", ".md")):
                chunks.append(zf.read(name).decode("utf-8", errors="ignore"))
    return "\n".join(chunks)


def snapshot_backup(destination_target, schedule_interval, user_handshake_token,
                    store, adapter=None):
    """Run one snapshot. Returns a payload; errors have status 'error'."""
    if not user_handshake_token or not str(user_handshake_token).strip():
        raise ValueError("user_handshake_token is required: backups need explicit user approval")
    destination = (destination_target or "").strip().lower()
    if destination not in DESTINATIONS:
        raise ValueError(f"unknown destination_target: {destination_target!r}; use supabase or drive")
    schedule = (schedule_interval or "7d").strip().lower()
    if schedule not in SCHEDULES:
        raise ValueError(f"unknown schedule_interval: {schedule_interval!r}; use 7d, 1d, 30d, or now")

    bundle, manifest = build_bundle(store)
    bundle_sha = hashlib.sha256(bundle).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Scrub gate: refuse before any upload if the bundle text holds a secret.
    if contains_secret(_bundle_text_for_scrub_gate(bundle), "standard"):
        return {
            "status": "error",
            "error": "snapshot refused: scrub gate found a secret in the bundle text; nothing was uploaded",
            "verified_callback": False,
            "backed_up": False,
        }

    # Local copy is always kept, so a failed upload loses nothing.
    local_dir = os.path.join(store.vault_dir, "snapshots")
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, f"hive-mind-{stamp}.zip")
    with open(local_path, "wb") as f:
        f.write(bundle)

    if adapter is None:
        # Local-only mode: verify by re-reading the local file.
        with open(local_path, "rb") as f:
            verified = hashlib.sha256(f.read()).hexdigest() == bundle_sha
        store.record_snapshot(destination, local_path, bundle_sha,
                              manifest["memory_count"], verified)
        return {
            "status": "local_only",
            "destination": destination,
            "schedule_interval": schedule,
            "storage_path": local_path,
            "sha256": bundle_sha,
            "memory_count": manifest["memory_count"],
            "verified_callback": verified,
            "backed_up": False,
            "note": "Live upload UNVERIFIED: no cloud adapter configured; local bundle only.",
        }

    storage_path = (
        f"hive-mind-snapshots/hive-mind-{stamp}.zip" if destination == "supabase"
        else f"hive-mind/hive-mind-{stamp}.zip"
    )
    try:
        adapter.upload(storage_path, bundle)
        downloaded = adapter.download(storage_path)
    except Exception as exc:  # upload/download failure: never backed up
        return {
            "status": "error",
            "error": f"snapshot upload/verification failed: {exc}",
            "verified_callback": False,
            "backed_up": False,
            "local_bundle_path": local_path,
            "storage_path": storage_path,
            "sha256": bundle_sha,
        }
    verified = hashlib.sha256(downloaded).hexdigest() == bundle_sha
    if not verified:
        return {
            "status": "error",
            "error": "snapshot verification failed: downloaded hash does not match the local bundle",
            "verified_callback": False,
            "backed_up": False,
            "local_bundle_path": local_path,
            "storage_path": storage_path,
            "sha256": bundle_sha,
        }
    store.record_snapshot(destination, storage_path, bundle_sha,
                          manifest["memory_count"], True)
    return {
        "status": "ok",
        "destination": destination,
        "schedule_interval": schedule,
        "storage_path": storage_path,
        "sha256": bundle_sha,
        "memory_count": manifest["memory_count"],
        "verified_callback": True,
        "backed_up": True,
        "local_bundle_path": local_path,
    }
