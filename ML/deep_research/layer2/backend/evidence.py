"""Rebuildable run-owned SQLite projections; source artifacts remain authoritative."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .fs import atomic_write_text, text_hash, storage_path
from .windows import text_pages


class EvidenceStore:
    """Input a run directory; index immutable pages and stream operational projections."""

    def __init__(self, run: Path):
        """Input one run; open its local index without loading corpus bodies."""
        self.run = storage_path(run)
        self.path = self.run / "_internal/trace/evidence.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.initialize()
        except sqlite3.DatabaseError as exc:
            if getattr(exc, "sqlite_errorcode", None) not in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB}:
                raise
            # Rebuild only the derived index; keep damaged bytes for diagnosis.
            suffix = ".damaged-" + uuid4().hex[:8]
            for name in ("evidence.sqlite3", "evidence.sqlite3-wal", "evidence.sqlite3-shm"):
                path = self.path.with_name(name)
                if path.exists():
                    path.replace(path.with_name(name + suffix))
            self.initialize()

    def initialize(self):
        """Input none; create rebuildable tables without touching authoritative run artifacts."""
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS blobs (hash TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS paths (path TEXT PRIMARY KEY, hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS members (
                    version TEXT, path TEXT, hash TEXT, PRIMARY KEY(version,path));
                CREATE TABLE IF NOT EXISTS records (
                    seq INTEGER PRIMARY KEY, collection TEXT, id TEXT, body TEXT,
                    UNIQUE(collection,id));
                CREATE INDEX IF NOT EXISTS records_order ON records(collection,seq);
                CREATE TABLE IF NOT EXISTS active_facts (seq INTEGER PRIMARY KEY, id TEXT UNIQUE);
                CREATE VIEW IF NOT EXISTS current_facts AS
                    SELECT a.seq,r.id,r.body FROM records r JOIN active_facts a ON a.id=r.id
                    WHERE r.collection='ledger';
                CREATE TABLE IF NOT EXISTS owners (
                    fact_id TEXT, domain_id TEXT, PRIMARY KEY(domain_id,fact_id));
                CREATE TABLE IF NOT EXISTS history_files (thread TEXT, id TEXT, PRIMARY KEY(thread,id));
                CREATE TABLE IF NOT EXISTS history_pages (
                    thread TEXT, path TEXT, hash TEXT, PRIMARY KEY(thread,path));
            """)

    @contextmanager
    def connect(self, *, read_only=False):
        """Input read intent; yield a fresh connection, with 5s read/60s write busy timeout."""
        db = sqlite3.connect(self.path, timeout=5 if read_only else 60)
        try:
            if read_only:
                db.execute("PRAGMA query_only=ON")
            with db:
                yield db
        finally:
            db.close()

    def clear(self, *collections):
        """Input transient collection names; rebuild projections without deleting source records."""
        with self.connect() as db:
            for name in collections:
                if name == "facts":
                    db.execute("DELETE FROM active_facts")
                else:
                    db.execute("DELETE FROM records WHERE collection=?", (name,))

    def put(self, collection, identity, value):
        """Input a projection key/value; store a JSON value for ordered bounded retrieval."""
        with self.connect() as db:
            if collection == "facts":
                db.execute("INSERT OR IGNORE INTO active_facts(id) VALUES(?)", (str(identity),))
                return
            body = json.dumps(value, ensure_ascii=False)
            db.execute("INSERT INTO records(collection,id,body) VALUES(?,?,?) "
                       "ON CONFLICT(collection,id) DO UPDATE SET body=excluded.body",
                       (collection, str(identity), body))

    def get(self, collection, identity):
        """Input a projection key; return its decoded value or None."""
        with self.connect() as db:
            if collection == "facts":
                row = db.execute("SELECT body FROM current_facts WHERE id=?", (str(identity),)).fetchone()
            else:
                row = db.execute("SELECT body FROM records WHERE collection=? AND id=?",
                                 (collection, str(identity))).fetchone()
        return json.loads(row[0]) if row else None

    def rows(self, collection):
        """Input a collection; yield one decoded record at a time in insertion order."""
        with self.connect() as db:
            rows = (db.execute("SELECT body FROM current_facts ORDER BY seq") if collection == "facts" else
                    db.execute("SELECT body FROM records WHERE collection=? ORDER BY seq", (collection,)))
            for row in rows:
                yield json.loads(row[0])

    def count(self, collection):
        """Input a collection; return its size without loading its records."""
        with self.connect() as db:
            if collection == "facts":
                return db.execute("SELECT count(*) FROM active_facts").fetchone()[0]
            return db.execute("SELECT count(*) FROM records WHERE collection=?", (collection,)).fetchone()[0]

    def add_text(self, label, text, *, previous=None, following=None):
        """Input a trusted label and text; index bounded pages with stable navigation links."""
        pages = text_pages(text)
        names = [f"/{label}/{i // 100:04d}/{i + 1:06d}.txt" for i in range(len(pages))]
        with self.connect() as db:
            db.execute("DELETE FROM paths WHERE substr(path,1,?)=?", (len(label) + 2, f"/{label}/"))
            for i, (name, body) in enumerate(zip(names, pages)):
                links = []
                if i:
                    links.append(f"Previous: /evidence{names[i - 1]}")
                if i + 1 < len(names):
                    links.append(f"Next: /evidence{names[i + 1]}")
                if links:
                    body += "\n\n[Navigation]\n" + "\n".join(links)
                if i == 0 and previous:
                    body += f"\nPrevious source window: /evidence/{previous}/"
                if i + 1 == len(names) and following:
                    body += f"\nNext source window: /evidence/{following}/"
                digest = text_hash(body)
                db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (digest, body))
                db.execute("INSERT OR REPLACE INTO paths VALUES(?,?)", (name, digest))

    def add_records(self, label, records):
        """Input ordered records; index each separately, retaining arbitrary JSON and identifiers."""
        with self.connect() as db:
            db.execute("DELETE FROM paths WHERE substr(path,1,?)=?", (len(label) + 2, f"/{label}/"))
        for i, value in enumerate(records):
            self.add_text(f"{label}/{i // 100:04d}/{i + 1:06d}", json.dumps(value, ensure_ascii=False))

    def snapshot(self):
        """Input none; freeze the accessible path/hash manifest, never hash corpus bodies per job."""
        digest = hashlib.sha256()
        with self.connect() as db:
            for path, value in db.execute("SELECT path,hash FROM paths ORDER BY path"):
                digest.update((path + "\0" + value + "\n").encode())
            version = digest.hexdigest()
            db.execute("INSERT OR IGNORE INTO members SELECT ?,path,hash FROM paths", (version,))
        return version

    def documents(self, version, prefix="/"):
        """Input immutable version and prefix; yield approved paths and bodies from that view."""
        with self.connect(read_only=True) as db:
            for path, body in db.execute(
                "SELECT m.path,b.body FROM members m JOIN blobs b ON m.hash=b.hash "
                "WHERE m.version=? AND substr(m.path,1,?)=? ORDER BY m.path",
                (version, len(prefix), prefix),
            ):
                yield path, body

    def names(self, version, prefix="/"):
        """Input version and directory; enumerate path metadata without loading evidence bodies."""
        with self.connect(read_only=True) as db:
            for row in db.execute("SELECT path FROM members WHERE version=? AND substr(path,1,?)=? ORDER BY path",
                                  (version, len(prefix), prefix)):
                yield row[0]

    def body(self, version, path):
        """Input version/path; return only a registered virtual document or None."""
        with self.connect(read_only=True) as db:
            row = db.execute("SELECT b.body FROM members m JOIN blobs b ON m.hash=b.hash "
                             "WHERE m.version=? AND m.path=?", (version, path)).fetchone()
        return row[0] if row else None

    def archive(self, thread, messages):
        """Input application thread and complete messages; durably archive exact JSON before eviction."""
        identity = text_hash(thread)[:20]
        text = json.dumps(messages, ensure_ascii=False)
        digest = text_hash(text)[:24]
        path = self.run / "_internal/trace/history" / identity / f"{digest}.json"
        owner = path.parent / ".session"
        if owner.exists() and owner.read_text(encoding="utf-8") != thread:
            raise OSError("history session identifier collision")
        if not owner.exists():
            atomic_write_text(owner, thread)
        if path.exists():
            if path.read_text(encoding="utf-8") != text:
                raise OSError("immutable history identifier collision")
        else:
            atomic_write_text(path, text)
        self.index_history(thread)
        return f"/history/{digest}/"

    def index_history(self, thread):
        """Input app thread; index missing immutable archive pages once, also after index recovery."""
        directory = self.run / "_internal/trace/history" / text_hash(thread)[:20]
        owner = directory / ".session"
        if not owner.exists() or owner.read_text(encoding="utf-8") != thread:
            return
        for path in sorted(directory.glob("*.json")):
            with self.connect() as db:
                if db.execute("SELECT 1 FROM history_files WHERE thread=? AND id=?", (thread, path.stem)).fetchone():
                    continue
                for i, page in enumerate(text_pages(path.read_text(encoding="utf-8"))):
                    digest = text_hash(page)
                    db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?)", (digest, page))
                    db.execute("INSERT OR REPLACE INTO history_pages VALUES(?,?,?)",
                               (thread, f"/{path.stem}/{i + 1:06d}.txt", digest))
                db.execute("INSERT INTO history_files VALUES(?,?)", (thread, path.stem))

    def history(self, thread, prefix="/", *, names_only=False):
        """Input app thread/prefix; yield scoped indexed pages or path metadata without corpus reads."""
        with self.connect(read_only=True) as db:
            columns = "p.path" if names_only else "p.path,b.body"
            join = "" if names_only else "JOIN blobs b ON p.hash=b.hash"
            rows = db.execute(f"SELECT {columns} FROM history_pages p {join} "
                              "WHERE thread=? AND substr(p.path,1,?)=? ORDER BY p.path",
                              (thread, len(prefix), prefix))
            for row in rows:
                yield row[0] if names_only else row
