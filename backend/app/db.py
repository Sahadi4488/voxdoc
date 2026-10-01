"""SQLite schema, per-request connections and query functions.

One connection per request (never a shared global): sqlite3 connections must
not be used from several threads at once, and FastAPI runs sync routes in a
threadpool. Always "?" placeholders, never string formatting (SQL injection).
"""
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

from app.config import settings
from app.services.splitter import Sentence

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
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
    PRIMARY KEY (doc_id, idx),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);
"""

# Shared by list_documents/get_document so both return the same shape
_DOCUMENT_SELECT = """
SELECT d.id, d.title, d.filename, d.created_at,
       (SELECT COUNT(*) FROM sentences s WHERE s.doc_id = d.id) AS sentence_count
FROM documents d
"""


def connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open the connection in a sync
    # dependency on one threadpool thread and run the route on another. Safe
    # because each connection belongs to exactly one request.
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # off by default, per connection
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")  # readers don't block the writer; persists in the file
        conn.executescript(SCHEMA)
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
                    sentences: list[Sentence]) -> int:
    """Insert a document and all its sentences in one transaction; returns the new id."""
    created_at = datetime.now(timezone.utc).isoformat()
    with conn:  # commit on success, roll back on any exception
        cur = conn.execute(
            "INSERT INTO documents (title, filename, stored_name, created_at) VALUES (?, ?, ?, ?)",
            (title, filename, stored_name, created_at),
        )
        doc_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO sentences (doc_id, idx, text, page) VALUES (?, ?, ?, ?)",
            [(doc_id, s.idx, s.text, s.page) for s in sentences],
        )
    return doc_id


def list_documents(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(_DOCUMENT_SELECT + " ORDER BY d.created_at DESC, d.id DESC").fetchall()
    return [dict(r) for r in rows]


def get_document(conn: sqlite3.Connection, doc_id: int, with_sentences: bool = True) -> dict | None:
    row = conn.execute(_DOCUMENT_SELECT + " WHERE d.id = ?", (doc_id,)).fetchone()
    if row is None:
        return None
    doc = dict(row)
    if with_sentences:
        doc["sentences"] = [dict(r) for r in conn.execute(
            "SELECT idx, text, page FROM sentences WHERE doc_id = ? ORDER BY idx", (doc_id,))]
    return doc
