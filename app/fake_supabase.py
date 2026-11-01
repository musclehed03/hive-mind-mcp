"""FAKE cloud adapters (Block 5). No network, no credentials, no SDK.

These in-memory adapters stand in for Supabase Storage and Google
Drive in every test and in the default local run. They record calls
so tests can assert uploads, downloads, and failures. A real adapter
must be supplied on Sonja's machine, after her Supabase project and
bucket exist, and must never be committed with keys in it. The LIVE
upload gate is UNVERIFIED here — see the README (Block 5 live gate).
"""

import hashlib


class FakeUploadError(Exception):
    """Raised by the fake adapter when a test arms a failure."""


class FakeBucketAdapter:
    """In-memory bucket: upload/download/list, with an arming failure."""

    def __init__(self, name):
        self.name = name
        self.objects = {}
        self.upload_count = 0
        self.download_count = 0
        self.fail_next_upload = False
        self.fail_next_download = False

    def upload(self, storage_path, data):
        if self.fail_next_upload:
            self.fail_next_upload = False
            raise FakeUploadError(f"fake {self.name} upload failed for {storage_path}")
        self.objects[storage_path] = bytes(data)
        self.upload_count += 1

    def download(self, storage_path):
        self.download_count += 1
        if self.fail_next_download:
            self.fail_next_download = False
            raise FakeUploadError(f"fake {self.name} download failed for {storage_path}")
        return self.objects[storage_path]

    def exists(self, storage_path):
        return storage_path in self.objects

    def sha256(self, storage_path):
        return hashlib.sha256(self.objects[storage_path]).hexdigest()


def fake_supabase_adapter():
    """Fake Supabase Storage bucket (private hive-mind-snapshots)."""
    return FakeBucketAdapter("supabase:hive-mind-snapshots")


def fake_drive_adapter():
    """Fake Google Drive folder for snapshots."""
    return FakeBucketAdapter("drive:hive-mind")
