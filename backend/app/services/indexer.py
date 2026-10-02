"""Chunk + embed a document into the chunks table. Idempotent and self-healing.

ensure_indexed() is safe to call any number of times, from any thread:
- chunks for the current model exist -> return at once;
- otherwise take the document's lock, check again (another thread may have
  just finished: double-checked locking, the Day 5 pattern), then chunk,
  embed and swap the rows in one transaction.

It runs as a background task right after an upload, and again before every
retrieval, so a failed or missing index fixes itself on the next question.
"""
import logging
import sqlite3
import threading
from collections import defaultdict

from app import db
from app.services.chunker import chunk
from app.services.embeddings import to_blob

log = logging.getLogger(__name__)

_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock_for(doc_pk: int) -> threading.Lock:
    with _locks_guard:  # defaultdict insertion itself isn't atomic across threads
        return _locks[doc_pk]


def ensure_indexed(conn: sqlite3.Connection, doc_pk: int, embedder) -> int:
    """Returns the number of chunks indexed for the embedder's model."""
    model = embedder.model_name
    if n := db.count_chunks(conn, doc_pk, model):
        return n
    with _lock_for(doc_pk):
        if n := db.count_chunks(conn, doc_pk, model):
            return n
        chunks = chunk(db.get_sentences(conn, doc_pk), count_tokens=embedder.count_tokens,
                       limit=embedder.max_tokens)
        if not chunks:
            return 0
        vectors = embedder.embed_documents([c.text for c in chunks])
        db.replace_chunks(conn, doc_pk, chunks, [to_blob(v) for v in vectors], model)
        return len(chunks)


def index_document(public_id: str, embedder) -> None:
    """Background task after an upload. Opens its own connection: the request's
    connection is already closed when this runs. Never raises: retrieval calls
    ensure_indexed again, so a failure here only costs time on the first question."""
    conn = db.connect()
    try:
        doc_pk = db.get_doc_pk(conn, public_id)
        if doc_pk is not None:
            ensure_indexed(conn, doc_pk, embedder)
    except Exception:
        log.exception("Background indexing failed for document %s", public_id)
    finally:
        conn.close()
