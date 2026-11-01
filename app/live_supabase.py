"""LIVE Supabase Storage adapter (env-gated; NEVER the default).

This module makes real HTTP calls to Supabase Storage, but only
when the factory in ``app/live_clients.py`` returns it: that happens
only when ``HIVE_MIND_LIVE=1`` and ``SUPABASE_URL`` plus
``SUPABASE_SERVICE_ROLE_KEY`` are present in the environment. Every
other path uses the in-memory fake adapter or the local-only
snapshot mode, and importing this module alone makes no network
call.

The interface matches ``FakeBucketAdapter`` in
``app/fake_supabase.py``: ``upload(storage_path, data)``,
``download(storage_path)``, ``exists(storage_path)``,
``sha256(storage_path)``, plus ``delete(storage_path)`` for
removing a test snapshot. The one extra method, ``delete``, is
the only operation beyond upload/download used here — no other
Supabase operation (tables, auth, realtime) is called.

Errors are raised as ``LiveSupabaseError`` with a clear message
(the adapter interface is exception-based, matching the fake,
which raises ``FakeUploadError``). ``snapshot_backup`` converts
those into error payloads, so a failed upload is never reported
as backed up. Error messages never contain a credential: only the
HTTP status, the request method, and the object path.

Credentials are read from the environment only, never from a
file, never logged, and never included in a request body or an
error message. They appear only in the ``apikey`` and
``Authorization`` headers.

Request shapes follow the Supabase Storage REST API: upload is
``POST /storage/v1/object/{bucket}/{object}`` with ``x-upsert``,
download is ``GET`` on the same URL, existence is ``HEAD``.
Delete follows the Storage REST convention used by storage-js:
``DELETE /storage/v1/object/{bucket}`` with a JSON body of
``{"prefixes": ["<object>"]}``. That delete shape is the one part
of this adapter not pinned by the repo's own docs: if the server
rejects it, delete the test object in the Supabase dashboard —
the snapshot payload's hash-check, not the delete, is the
verification. The bucket defaults to ``hive-mind-snapshots`` and
can be changed with ``HIVE_MIND_SUPABASE_BUCKET``.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request

DEFAULT_BUCKET = "hive-mind-snapshots"


class LiveSupabaseError(Exception):
    """A live Supabase Storage call failed. Message holds no secret."""


class LiveSupabaseBucketAdapter:
    """Supabase Storage bucket adapter. Same interface as the fake."""

    def __init__(self, bucket=None):
        # Environment only. No file is ever read for a credential.
        self.base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        self.bucket = (
            bucket or os.environ.get("HIVE_MIND_SUPABASE_BUCKET") or DEFAULT_BUCKET
        )
        self.name = f"supabase:{self.bucket}"
        self.upload_count = 0
        self.download_count = 0

    # -- helpers ----------------------------------------------------------

    def _require_config(self):
        if not self.base_url or not self.service_role_key:
            raise LiveSupabaseError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must both be "
                "set in the environment; no Supabase request was attempted"
            )

    def _object_path(self, storage_path):
        path = (storage_path or "").strip().lstrip("/")
        prefix = self.bucket + "/"
        if path.startswith(prefix):
            path = path[len(prefix):]
        if not path or path == self.bucket:
            raise LiveSupabaseError("storage_path must name an object in the bucket")
        if ".." in path.split("/"):
            raise LiveSupabaseError("storage_path must not contain '..'")
        return path

    def _url(self, object_path):
        return f"{self.base_url}/storage/v1/object/{self.bucket}/{object_path}"

    def _headers(self, content_type=None):
        headers = {
            "apikey": self.service_role_key,
            "Authorization": "Bearer " + self.service_role_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request(self, method, url, data=None, headers=None):
        """One HTTP attempt, no retries. Returns (status, body bytes)."""
        request = urllib.request.Request(
            url, data=data, method=method, headers=headers or {}
        )
        try:
            response = urllib.request.urlopen(request, timeout=30)
            try:
                return response.status, response.read()
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
            raise LiveSupabaseError(
                f"Supabase Storage HTTP {exc.code} for {method}: {detail}".strip()
            ) from exc
        except urllib.error.URLError as exc:
            raise LiveSupabaseError(
                f"Supabase Storage request failed: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise LiveSupabaseError(
                f"Supabase Storage request failed: {type(exc).__name__}"
            ) from exc

    # -- FakeBucketAdapter interface --------------------------------------

    def upload(self, storage_path, data):
        """Upload bytes. Raises LiveSupabaseError on any failure."""
        self._require_config()
        object_path = self._object_path(storage_path)
        headers = self._headers("application/octet-stream")
        headers["x-upsert"] = "true"
        status, _body = self._request(
            "POST", self._url(object_path), data=bytes(data), headers=headers
        )
        if status not in (200, 201):
            raise LiveSupabaseError(
                f"Supabase Storage upload returned HTTP {status}"
            )
        self.upload_count += 1

    def download(self, storage_path):
        """Download bytes. Raises LiveSupabaseError, incl. on 404."""
        self._require_config()
        object_path = self._object_path(storage_path)
        try:
            status, body = self._request(
                "GET", self._url(object_path), headers=self._headers()
            )
        except LiveSupabaseError as exc:
            if "HTTP 404" in str(exc):
                raise LiveSupabaseError(
                    f"Supabase Storage object not found: {object_path}"
                ) from exc
            raise
        if status != 200:
            raise LiveSupabaseError(
                f"Supabase Storage download returned HTTP {status}"
            )
        self.download_count += 1
        return body

    def exists(self, storage_path):
        """True when the object exists; False on 404; error otherwise."""
        self._require_config()
        object_path = self._object_path(storage_path)
        try:
            status, _body = self._request(
                "HEAD", self._url(object_path), headers=self._headers()
            )
        except LiveSupabaseError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise
        return status == 200

    def sha256(self, storage_path):
        """SHA-256 of the object, via download (same value as the fake)."""
        return hashlib.sha256(self.download(storage_path)).hexdigest()

    def delete(self, storage_path):
        """Delete one object (test-snapshot cleanup). See module
        docstring for the delete-shape note."""
        self._require_config()
        object_path = self._object_path(storage_path)
        body = json.dumps({"prefixes": [object_path]}).encode("utf-8")
        status, _body = self._request(
            "DELETE",
            f"{self.base_url}/storage/v1/object/{self.bucket}",
            data=body,
            headers=self._headers("application/json"),
        )
        if status not in (200, 204):
            raise LiveSupabaseError(
                f"Supabase Storage delete returned HTTP {status}"
            )
