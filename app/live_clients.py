"""Env-gated factory: fake clients by default, live only on opt-in.

This is the single switch between fake and live. The default is
ALWAYS the fake clients, whatever else is configured: with
``HIVE_MIND_LIVE`` unset or anything other than ``"1"``, behaviour
is byte-identical to before this module existed — the fake Meta
client answers verification calls and snapshots run local-only.

Live clients are returned only when ``HIVE_MIND_LIVE=1``:

* Meta: a ``LiveMetaClient`` is returned whenever the flag is set,
  even if ``META_API_KEY`` is missing — the live client then
  returns a clear error dict on every call and makes no network
  attempt, so a missing key can never silently fall back to a
  fake success.
* Supabase: a ``LiveSupabaseBucketAdapter`` is returned only when
  the flag is set AND ``SUPABASE_URL`` and
  ``SUPABASE_SERVICE_ROLE_KEY`` are both present. Otherwise the
  snapshot path gets ``None`` and runs local-only, saying so in
  its payload — a missing credential never silently becomes a
  fake upload.

No key is read, stored, or logged here; the live clients read
their own credentials from the environment. Importing this module
makes no network call.
"""

import os

from .fake_meta import FakeMetaClient
from .live_meta import LiveMetaClient
from .live_supabase import LiveSupabaseBucketAdapter


def live_enabled():
    """True only when HIVE_MIND_LIVE is exactly "1"."""
    return os.environ.get("HIVE_MIND_LIVE") == "1"


def get_meta_client():
    """Fake client by default; live client only when opted in."""
    if live_enabled():
        return LiveMetaClient()
    return FakeMetaClient()


def get_snapshot_adapter(destination_target):
    """Live Supabase adapter only for supabase + flag + credentials.

    Returns None for every other case (including the Drive
    destination, which has no live adapter in this codebase), which
    makes ``snapshot_backup`` run in its local-only mode.
    """
    if not live_enabled():
        return None
    if (destination_target or "").strip().lower() != "supabase":
        return None
    if not os.environ.get("SUPABASE_URL") or not os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    ):
        return None
    return LiveSupabaseBucketAdapter()
