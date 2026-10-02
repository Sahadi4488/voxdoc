"""Top-k chunk retrieval with NumPy.

A document has a few hundred chunks at most, so a brute-force dot product
over all of them takes well under a millisecond: no vector database, and no
in-memory cache (loading the vectors from SQLite takes milliseconds).
"""
import sqlite3
from dataclasses import dataclass

import numpy as np

from app import db
from app.services.embeddings import from_blob
from app.services.indexer import ensure_indexed


@dataclass(frozen=True)
class Hit:
    chunk_idx: int
    start_idx: int  # sentence range, inclusive: what Day 13 cites
    end_idx: int
    text: str
    score: float  # cosine similarity in [-1, 1]


def retrieve(conn: sqlite3.Connection, doc_pk: int, question: str, embedder, k: int = 4) -> list[Hit]:
    """The k chunks most similar to the question, best first."""
    ensure_indexed(conn, doc_pk, embedder)  # self-heals a missing or stale index
    rows = db.get_chunks(conn, doc_pk, embedder.model_name)
    if not rows or k <= 0:
        return []
    matrix = np.stack([from_blob(r["embedding"]) for r in rows])  # (n, dim)
    scores = matrix @ embedder.embed_query(question)  # unit vectors: dot product = cosine
    k = min(k, len(rows))  # argpartition raises when k > n
    top = np.argpartition(-scores, k - 1)[:k]  # the k best in O(n), unordered
    top = top[np.argsort(-scores[top])]  # then order just those k
    return [
        Hit(rows[i]["idx"], rows[i]["start_idx"], rows[i]["end_idx"], rows[i]["text"], float(scores[i]))
        for i in top
    ]
