"""Chunk + embed a document into the chunks table. Idempotent and self-healing.

ensure_indexed() is safe to call any number of times, from any thread:
- chunks for the current model exist -> return at once;
- otherwise take the document's lock, check again (another thread may have
  just finished: double-checked locking, app/utils/locks.py), then chunk,
  embed and swap the rows in one transaction.

It runs as a background task right after an upload, and again before every
retrieval, so a failed or missing index fixes itself on the next question.
"""
import logging
import sqlite3

from app import db
from app.services.chunker import chunk
from app.services.embeddings import to_blob
from app.utils.locks import KeyedLock

log = logging.getLogger(__name__)

_index_locks = KeyedLock()


def ensure_indexed(conn: sqlite3.Connection, doc_pk: int, embedder) -> int:
    """Returns the number of chunks indexed for the embedder's model."""
    model = embedder.model_name

    def create() -> int:
        chunks = chunk(db.get_sentences(conn, doc_pk), count_tokens=embedder.count_tokens,
                       limit=embedder.max_tokens)
        if not chunks:
            return 0
        vectors = embedder.embed_documents([c.text for c in chunks])
        db.replace_chunks(conn, doc_pk, chunks, [to_blob(v) for v in vectors], model)
        return len(chunks)

    return _index_locks.get_or_create(doc_pk, lambda: db.count_chunks(conn, doc_pk, model) or None, create)


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
