"""SQLite schema, per-request connections and query functions.

One connection per request (never a shared global): sqlite3 connections must
not be used from several threads at once, and FastAPI runs sync routes in a
threadpool. Always "?" placeholders, never string formatting (SQL injection).

Documents have an internal integer id (joins, foreign keys) and an unguessable
public_id. Only public_id ever leaves this module: sequential ids in URLs
would let any visitor read everyone's documents by counting (IDOR).
"""
import secrets
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

from app.config import settings
from app.services.splitter import Sentence

SCHEMA_VERSION = 2  # 2: public_id, sentences.para

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
"""

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
        if has_tables and version != SCHEMA_VERSION:
            raise SchemaMismatchError(
                f"{settings.db_path} has schema version {version}, this code needs {SCHEMA_VERSION}. "
                "It only holds development data: delete it (and data/uploads) and restart."
            )
        conn.execute("PRAGMA journal_mode = WAL")  # readers don't block the writer; persists in the file
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
