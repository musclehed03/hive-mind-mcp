"""Block 1 foundation primitives: remember / recall / forget / memory_stats.

Storage is local-first, mirroring the memory-layer base this was built from:

* SQLite is the source of truth. When the ``sqlite_vec`` extension loads,
  a ``vec0`` table is created so later blocks can store embeddings in the
  same database. Block 1 stores no embeddings and makes no embedding calls:
  the vector table stays empty until a later block wires an embedder in.
* The vault is a mirror, not a second source of truth: every write appends
  one JSON line to ``vault/memories.jsonl`` and writes one Markdown note to
  ``vault/memories/<id>.md`` (Obsidian-compatible frontmatter). Forgets
  append a tombstone line and remove the note, keeping the audit trail.
* Recall in Block 1 is lexical (token overlap), computed where the data
  lives in SQLite. Vector recall is a later block; nothing here pretends
  otherwise, and nothing here touches the network.

The store is deliberately boring and synchronous: no polling, no
background threads, no always-on work (Pillar 2, event-driven spiking).
"""

import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from .config import DB_PATH, EMBED_DIM, VAULT_DIR

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text):
    return set(_TOKEN_RE.findall(text.lower()))


class Store:
    """A single SQLite database + vault mirror. Create, use, close."""

    def __init__(self, db_path=None, vault_dir=None, embed_dim=None, use_vec=None):
        self.db_path = db_path or DB_PATH
        self.vault_dir = vault_dir or VAULT_DIR
        self.embed_dim = embed_dim or EMBED_DIM
        self._lock = threading.Lock()
        self._conn = None
        # use_vec=None means auto-detect: try to load sqlite-vec, fall back
        # cleanly if the extension is unavailable on this machine.
        self._want_vec = True if use_vec is None else bool(use_vec)
        self.vec_available = False
        self._connect()

    # -- connection -----------------------------------------------------

    def _connect(self):
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        if self._want_vec:
            try:
                conn.enable_load_extension(True)
                try:
                    import sqlite_vec

                    sqlite_vec.load(conn)
                    self.vec_available = True
                finally:
                    conn.enable_load_extension(False)
            except Exception:
                self.vec_available = False
        conn.execute(
            "CREATE TABLE IF NOT EXISTS memories("
            "id TEXT PRIMARY KEY, text TEXT NOT NULL, entities TEXT NOT NULL, "
            "source TEXT NOT NULL DEFAULT '', domain TEXT NOT NULL DEFAULT '', "
            "status TEXT NOT NULL DEFAULT 'active', "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        # Block 3/4 columns, added idempotently so Block 1 databases
        # migrate in place instead of being rebuilt.
        _existing = {r[1] for r in conn.execute("PRAGMA table_info(memories)")}
        for _col, _ddl in (
            ("provenance", "TEXT NOT NULL DEFAULT '{}'"),
            ("superseded_by", "TEXT NOT NULL DEFAULT ''"),
        ):
            if _col not in _existing:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {_col} {_ddl}")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS changelog("
            "id TEXT PRIMARY KEY, event TEXT NOT NULL, old_id TEXT NOT NULL, "
            "new_id TEXT NOT NULL, diff TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS snapshots("
            "id TEXT PRIMARY KEY, destination TEXT NOT NULL, storage_path TEXT NOT NULL, "
            "sha256 TEXT NOT NULL, memory_count INTEGER NOT NULL, "
            "verified_callback INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)"
        )
        if self.vec_available:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS vecs "
                f"USING vec0(embedding float[{self.embed_dim}])"
            )
        conn.commit()
        self._conn = conn

    def close(self):
        if self._conn is not None:
            with self._lock:
                self._conn.commit()
                self._conn.close()
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- vault mirror ---------------------------------------------------

    def _vault_paths(self, mid):
        notes_dir = os.path.join(self.vault_dir, "memories")
        return (
            os.path.join(self.vault_dir, "memories.jsonl"),
            os.path.join(notes_dir, f"{mid}.md"),
            notes_dir,
        )

    def _vault_append(self, record):
        jsonl_path, _, _ = self._vault_paths(record["id"])
        os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def _vault_write_note(self, mid, text, entities, source, domain, created_at):
        _, note_path, notes_dir = self._vault_paths(mid)
        os.makedirs(notes_dir, exist_ok=True)
        links = " ".join(f"[[{e}]]" for e in entities)
        body = (
            f"---\nid: {mid}\nsource: {source}\ndomain: {domain}\n"
            f"created: {created_at}\n---\n\n{text}\n"
        )
        if links:
            body += f"\n{links}\n"
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(body)

    # -- primitives -----------------------------------------------------

    def remember(self, text, entities=None, source="", domain="",
                   provenance=None, created_at=None):
        """Store one fact. Returns its id. Raises ValueError on empty text.

        Block 3 additions: ``provenance`` (OKF trust-signal dict, stored
        as JSON) and ``created_at`` (ISO timestamp; callers that backfill
        older facts pass it explicitly so the temporal tiers are honest).
        """
        if not text or not text.strip():
            raise ValueError("text must not be empty")
        entities = list(entities or [])
        mid = uuid.uuid4().hex
        now = created_at or datetime.now(timezone.utc).isoformat()
        prov = json.dumps(provenance or {}, sort_keys=True)
        with self._lock:
            self._conn.execute(
                "INSERT INTO memories(id, text, entities, source, domain, "
                "status, created_at, updated_at, provenance, superseded_by) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (mid, text, json.dumps(entities), source, domain, "active",
                 now, now, prov, ""),
            )
            self._conn.commit()
        record = {
            "event": "remember", "id": mid, "text": text, "entities": entities,
            "source": source, "domain": domain, "status": "active",
            "created_at": now, "provenance": provenance or {},
        }
        self._vault_append(record)
        self._vault_write_note(mid, text, entities, source, domain, now)
        return mid

    # -- Block 3/4 reads, supersede, changelog, snapshots ------------

    def get_memory(self, memory_id):
        """One memory as a dict, or None. Includes provenance + status."""
        row = self._conn.execute(
            "SELECT id, text, entities, source, domain, status, created_at, "
            "updated_at, provenance, superseded_by FROM memories WHERE id=?",
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row):
        return {
            "id": row[0], "text": row[1], "entities": json.loads(row[2]),
            "source": row[3], "domain": row[4], "status": row[5],
            "created_at": row[6], "updated_at": row[7],
            "provenance": json.loads(row[8] or "{}"),
            "superseded_by": row[9],
        }

    def list_memories(self, domain="", status="active", limit=100):
        """Active (or given-status) memories, most recent first."""
        rows = self._conn.execute(
            "SELECT id, text, entities, source, domain, status, created_at, "
            "updated_at, provenance, superseded_by FROM memories "
            "WHERE (?='' OR domain=?) AND status=? "
            "ORDER BY created_at DESC LIMIT ?",
            (domain, domain, status, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def supersede(self, old_id, new_id, diff_text):
        """Mark old_id superseded by new_id and append a changelog entry.

        Non-destructive: the old row stays for audit, recall only returns
        active rows. Returns True if old_id existed and was active.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE memories SET status='superseded', superseded_by=?, "
                "updated_at=? WHERE id=? AND status='active'",
                (new_id, now, old_id),
            )
            if cur.rowcount == 0:
                self._conn.commit()
                return False
            self._conn.execute(
                "INSERT INTO changelog(id, event, old_id, new_id, diff, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (uuid.uuid4().hex, "supersede", old_id, new_id, diff_text, now),
            )
            self._conn.commit()
        return True

    def changelog(self, limit=20):
        rows = self._conn.execute(
            "SELECT id, event, old_id, new_id, diff, created_at FROM changelog "
            "ORDER BY created_at DESC LIMIT ?", (limit,),
        ).fetchall()
        return [
            {"id": r[0], "event": r[1], "old_id": r[2], "new_id": r[3],
             "diff": r[4], "created_at": r[5]}
            for r in rows
        ]

    def record_snapshot(self, destination, storage_path, sha256, memory_count,
                        verified_callback):
        sid = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO snapshots(id, destination, storage_path, sha256, "
                "memory_count, verified_callback, created_at) VALUES (?,?,?,?,?,?,?)",
                (sid, destination, storage_path, sha256, memory_count,
                 1 if verified_callback else 0, now),
            )
            self._conn.commit()
        return sid

    def recall(self, query, limit=5):
        """Lexical recall: memories sharing tokens with the query, best first.

        Block 1 only. Vector recall arrives with the embedding wiring in a
        later block; this fallback keeps recall working with zero network
        and zero local model, and is honest about what it is.
        """
        if limit is None or limit < 1:
            limit = 5
        query_tokens = _tokens(query or "")
        rows = self._conn.execute(
            "SELECT id, text, entities, source, domain, created_at "
            "FROM memories WHERE status='active' ORDER BY created_at DESC"
        ).fetchall()
        scored = []
        for row in rows:
            overlap = len(query_tokens & _tokens(row[1]))
            if query_tokens and overlap == 0:
                continue
            scored.append((overlap, row))
        # Highest overlap first; most recent wins ties.
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "id": r[0], "text": r[1], "entities": json.loads(r[2]),
                "source": r[3], "domain": r[4], "created_at": r[5],
                "score": overlap / max(len(query_tokens), 1),
            }
            for overlap, r in scored[:limit]
        ]

    def forget(self, memory_id):
        """Delete one memory. Returns True if it existed, False otherwise."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM memories WHERE id=?", (memory_id,)
            )
            # No vector rows are written in Block 1, so there is nothing
            # to remove from vecs here. A later block that writes embeddings
            # must delete the matching vec row before this DELETE.
            self._conn.commit()
            deleted = cur.rowcount > 0
        if deleted:
            jsonl_path, note_path, _ = self._vault_paths(memory_id)
            self._vault_append({
                "event": "forget", "id": memory_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            try:
                os.remove(note_path)
            except OSError:
                pass
            _ = jsonl_path
        return deleted

    def memory_stats(self):
        """Counts for the store, plus whether sqlite-vec loaded."""
        total = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_domain = {
            r[0]: r[1]
            for r in self._conn.execute(
                "SELECT domain, COUNT(*) FROM memories GROUP BY domain"
            )
        }
        last_24h = self._conn.execute(
            "SELECT COUNT(*) FROM memories WHERE created_at > datetime('now','-1 day')"
        ).fetchone()[0]
        by_status = {
            r[0]: r[1]
            for r in self._conn.execute(
                "SELECT status, COUNT(*) FROM memories GROUP BY status"
            )
        }
        return {
            "total": total,
            "by_domain": by_domain,
            "by_status": by_status,
            "active": by_status.get("active", 0),
            "last_24h": last_24h,
            "vec_available": self.vec_available,
        }
