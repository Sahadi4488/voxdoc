"""SQLite schema, per-request connections and query functions.

One connection per request (never a shared global): sqlite3 connections must
not be used from several threads at once, and FastAPI runs sync routes in a
threadpool. Always "?" placeholders, never string formatting (SQL injection).

Documents have an internal integer id (joins, foreign keys) and an unguessable
public_id. Only public_id ever leaves this module: sequential ids in URLs
would let any visitor read everyone's documents by counting (IDOR).
"""
import json
import secrets
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

from app.config import settings
from app.services.splitter import Sentence

SCHEMA_VERSION = 4  # 2: public_id, sentences.para; 3: chunks; 4: summaries

CHUNKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    doc_id    INTEGER NOT NULL,
    idx       INTEGER NOT NULL,
    text      TEXT NOT NULL,
    start_idx INTEGER NOT NULL,         -- first sentence (inclusive): chunks are citable sentence ranges
    end_idx   INTEGER NOT NULL,         -- last sentence (inclusive)
    embedding BLOB NOT NULL,            -- float32 vector, L2-normalised
    model     TEXT NOT NULL,            -- vectors from different models aren't comparable: re-index on change
    PRIMARY KEY (doc_id, idx),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
"""

SUMMARIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS summaries (
    doc_id     INTEGER PRIMARY KEY,     -- one summary per document, generated once
    overview   TEXT NOT NULL,
    key_points TEXT NOT NULL,           -- JSON array of strings
    source     TEXT NOT NULL,           -- 'full' text, or 'excerpts' of a long document
    model      TEXT NOT NULL,
    created_at TEXT NOT NULL,           -- ISO-8601 UTC
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
"""

# from_version -> SQL that brings a database to from_version + 1
MIGRATIONS = {2: CHUNKS_SCHEMA, 3: SUMMARIES_SCHEMA}

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    public_id   TEXT NOT NULL UNIQUE,   -- secrets.token_urlsafe(8); the only id the API exposes
    title       TEXT NOT NULL,
    filename    TEXT NOT NULL,          -- original client filename, display only
    stored_name TEXT NOT NULL UNIQUE,   -- <uuid>.<ext> in upload_dir
    created_at  TEXT NOT NULL           -- ISO-8601 UTC
);

CREATE TABLE IF NOT EXISTS sentences (
    doc_id INTEGER NOT NULL,
    idx    INTEGER NOT NULL,
    text   TEXT NOT NULL,
    page   INTEGER,                     -- NULL for DOCX
    para   INTEGER NOT NULL,            -- paragraph number; the Reader groups by it
    PRIMARY KEY (doc_id, idx),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
""" + CHUNKS_SCHEMA + SUMMARIES_SCHEMA

_DOCUMENT_SELECT = """
SELECT d.id AS _pk, d.public_id AS id, d.title, d.filename, d.created_at,
       (SELECT COUNT(*) FROM sentences s WHERE s.doc_id = d.id) AS sentence_count
FROM documents d
"""


class SchemaMismatchError(RuntimeError):
    pass


def connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open the connection in a sync
    # dependency on one threadpool thread and run the route on another. Safe
    # because each connection belongs to exactly one request.
    # timeout=10: wait up to 10 s for another writer instead of failing at once
    # with "database is locked" when two uploads finish together.
    conn = sqlite3.connect(settings.db_path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # off by default, per connection
    return conn


def init_db() -> None:
    conn = connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        has_tables = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'documents'").fetchone()
        conn.execute("PRAGMA journal_mode = WAL")  # readers don't block the writer; persists in the file
        if has_tables and version != SCHEMA_VERSION:
            if not all(v in MIGRATIONS for v in range(version, SCHEMA_VERSION)):
                raise SchemaMismatchError(
                    f"{settings.db_path} has schema version {version}, this code needs {SCHEMA_VERSION}. "
                    "It only holds development data: delete it (and data/uploads) and restart."
                )
            for v in range(version, SCHEMA_VERSION):
                conn.executescript(MIGRATIONS[v])
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")  # PRAGMA can't take "?"; constant int
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, always closed."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def insert_document(conn: sqlite3.Connection, title: str, filename: str, stored_name: str,
                    sentences: list[Sentence]) -> str:
    """Insert a document and all its sentences in one transaction; returns its public_id."""
    created_at = datetime.now(timezone.utc).isoformat()
    public_id = secrets.token_urlsafe(8)  # 64 random bits; a collision fails the UNIQUE constraint
    with conn:  # commit on success, roll back on any exception
        cur = conn.execute(
            "INSERT INTO documents (public_id, title, filename, stored_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (public_id, title, filename, stored_name, created_at),
        )
        doc_pk = cur.lastrowid
        conn.executemany(
            "INSERT INTO sentences (doc_id, idx, text, page, para) VALUES (?, ?, ?, ?, ?)",
            [(doc_pk, s.idx, s.text, s.page, s.para) for s in sentences],
        )
    return public_id


def get_sentence_text(conn: sqlite3.Connection, public_id: str, idx: int) -> str | None:
    row = conn.execute(
        "SELECT s.text FROM sentences s JOIN documents d ON d.id = s.doc_id WHERE d.public_id = ? AND s.idx = ?",
        (public_id, idx),
    ).fetchone()
    return row["text"] if row else None


def get_document(conn: sqlite3.Connection, public_id: str, with_sentences: bool = True) -> dict | None:
    row = conn.execute(_DOCUMENT_SELECT + " WHERE d.public_id = ?", (public_id,)).fetchone()
    if row is None:
        return None
    doc = dict(row)
    pk = doc.pop("_pk")
    if with_sentences:
        doc["sentences"] = [dict(r) for r in conn.execute(
            "SELECT idx, text, page, para FROM sentences WHERE doc_id = ? ORDER BY idx", (pk,))]
    return doc


# --------------------------------------------------------------------------- retrieval (Day 11)
# These take the internal integer key: they're called by services, never with user input directly.

def get_doc_pk(conn: sqlite3.Connection, public_id: str) -> int | None:
    row = conn.execute("SELECT id FROM documents WHERE public_id = ?", (public_id,)).fetchone()
    return row["id"] if row else None


def get_sentences(conn: sqlite3.Connection, doc_pk: int) -> list[Sentence]:
    rows = conn.execute("SELECT idx, text, page, para FROM sentences WHERE doc_id = ? ORDER BY idx", (doc_pk,))
    return [Sentence(r["idx"], r["text"], r["page"], r["para"]) for r in rows]


def count_chunks(conn: sqlite3.Connection, doc_pk: int, model: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM chunks WHERE doc_id = ? AND model = ?", (doc_pk, model)).fetchone()[0]


def replace_chunks(conn: sqlite3.Connection, doc_pk: int, chunks, blobs: list[bytes], model: str) -> None:
    """Swap a document's chunks for new ones in one transaction (old model's included)."""
    with conn:
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_pk,))
        conn.executemany(
            "INSERT INTO chunks (doc_id, idx, text, start_idx, end_idx, embedding, model) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(doc_pk, c.idx, c.text, c.start_idx, c.end_idx, blob, model) for c, blob in zip(chunks, blobs)],
        )


def get_chunks(conn: sqlite3.Connection, doc_pk: int, model: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT idx, text, start_idx, end_idx, embedding FROM chunks WHERE doc_id = ? AND model = ? ORDER BY idx",
        (doc_pk, model),
    ).fetchall()


# --------------------------------------------------------------------------- summaries (Day 12)

def get_summary(conn: sqlite3.Connection, doc_pk: int) -> dict | None:
    row = conn.execute("SELECT overview, key_points, source, model, created_at FROM summaries WHERE doc_id = ?",
                       (doc_pk,)).fetchone()
    return {**dict(row), "key_points": json.loads(row["key_points"])} if row else None


def save_summary(conn: sqlite3.Connection, doc_pk: int, overview: str, key_points: list[str],
                 source: str, model: str) -> dict:
    summary = {"overview": overview, "key_points": key_points, "source": source, "model": model,
               "created_at": datetime.now(timezone.utc).isoformat()}
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO summaries (doc_id, overview, key_points, source, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc_pk, overview, json.dumps(key_points), source, model, summary["created_at"]),
        )
    return summary
