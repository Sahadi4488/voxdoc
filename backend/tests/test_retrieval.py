import sqlite3
import threading
import time

import numpy as np
import pytest

from app import db
from app.config import settings
from app.services.embeddings import from_blob, to_blob
from app.services.indexer import ensure_indexed
from app.services.retriever import retrieve
from app.services.splitter import Sentence
from tests.conftest import FIXTURES, FakeEmbedder, upload


def make_doc(texts, paras=None):
    """Insert a document straight into the (temporary) database; returns its pk."""
    db.init_db()
    conn = db.connect()
    sentences = [Sentence(i, t, None, (paras or [0] * len(texts))[i]) for i, t in enumerate(texts)]
    public_id = db.insert_document(conn, "t", "t.pdf", f"{len(texts)}-{time.time_ns()}.pdf", sentences)
    pk = db.get_doc_pk(conn, public_id)
    conn.close()
    return pk


def chunk_rows(pk):
    conn = db.connect()
    rows = conn.execute("SELECT idx, model FROM chunks WHERE doc_id = ?", (pk,)).fetchall()
    conn.close()
    return rows


def test_blob_round_trip_is_exact():
    v = np.random.default_rng(0).standard_normal(384).astype(np.float32)
    back = from_blob(to_blob(v))
    assert back.dtype == np.float32 and back.shape == (384,) and np.array_equal(back, v)


def test_float64_is_stored_as_float32():
    v = np.random.default_rng(1).standard_normal(384)  # float64
    back = from_blob(to_blob(v))
    assert back.shape == (384,) and np.allclose(back, v, atol=1e-6)


def test_ensure_indexed_twice_does_not_duplicate():
    pk = make_doc([f"Sentence number {i} about topic {i % 3}." for i in range(40)])
    e = FakeEmbedder()
    conn = db.connect()
    n1 = ensure_indexed(conn, pk, e)
    n2 = ensure_indexed(conn, pk, e)
    conn.close()
    assert n1 == n2 == len(chunk_rows(pk)) and e.document_calls == 1


def test_concurrent_first_questions_index_once():
    pk = make_doc([f"Sentence {i}." for i in range(30)])
    e = FakeEmbedder()
    slow_embed = e.embed_documents
    e.embed_documents = lambda texts: (time.sleep(0.2), slow_embed(texts))[1]
    errors = []

    def worker():
        conn = db.connect()
        try:
            ensure_indexed(conn, pk, e)
        except Exception as ex:  # noqa: BLE001
            errors.append(ex)
        finally:
            conn.close()
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and e.document_calls == 1


def test_model_change_reindexes():
    pk = make_doc(["Alpha beta.", "Gamma delta."])
    old, new = FakeEmbedder(), FakeEmbedder()
    new.model_name = "fake-bow-v2"
    conn = db.connect()
    ensure_indexed(conn, pk, old)
    ensure_indexed(conn, pk, new)
    conn.close()
    assert {r["model"] for r in chunk_rows(pk)} == {"fake-bow-v2"}  # old vectors replaced, never mixed


def test_retrieve_orders_by_score(monkeypatch):
    from app.services import chunker
    monkeypatch.setattr(chunker, "TARGET_TOKENS", 1)  # one sentence per chunk: easy to reason about
    texts = ["The cat sat on the mat.", "Interest rates rose in March.", "Dogs chase cats in the park.",
             "The central bank raised interest rates again."]
    pk = make_doc(texts)
    conn = db.connect()
    hits = retrieve(conn, pk, "interest rates bank", FakeEmbedder(), k=2)
    conn.close()
    assert [h.start_idx for h in hits] == [3, 1]
    assert hits[0].score >= hits[1].score and all(-1 <= h.score <= 1 for h in hits)


def test_k_larger_than_chunk_count():
    pk = make_doc(["Only one short sentence."])
    conn = db.connect()
    hits = retrieve(conn, pk, "short sentence", FakeEmbedder(), k=10)
    conn.close()
    assert len(hits) == 1 and (hits[0].start_idx, hits[0].end_idx) == (0, 0)


def test_empty_document_returns_nothing():
    pk = make_doc([])
    conn = db.connect()
    assert retrieve(conn, pk, "anything", FakeEmbedder()) == []
    conn.close()


def test_upload_indexes_in_the_background_when_enabled(client, fake_embedder, monkeypatch):
    monkeypatch.setattr(settings, "index_on_upload", True)
    doc = upload(client, FIXTURES / "sample.docx").json()  # TestClient runs background tasks before returning
    conn = db.connect()
    pk = db.get_doc_pk(conn, doc["id"])
    rows = db.get_chunks(conn, pk, "fake-bow")
    conn.close()
    assert rows and rows[0]["start_idx"] == 0 and rows[-1]["end_idx"] == doc["sentence_count"] - 1


def test_default_indexes_lazily_on_first_question(client):
    doc = upload(client, FIXTURES / "sample.docx").json()
    conn = db.connect()
    pk = db.get_doc_pk(conn, doc["id"])
    assert db.count_chunks(conn, pk, "fake-bow") == 0
    assert retrieve(conn, pk, "How much did the U.S. grow?", FakeEmbedder())  # lazily indexed on first question
    conn.close()


def test_background_failure_does_not_break_upload(client, fake_embedder, monkeypatch):
    monkeypatch.setattr(settings, "index_on_upload", True)

    def boom(texts):
        raise RuntimeError("model crashed")
    fake_embedder.embed_documents = boom
    r = upload(client, FIXTURES / "sample.docx")
    assert r.status_code == 201


def test_deleting_a_document_deletes_its_chunks(client):
    doc = upload(client, FIXTURES / "sample.docx").json()
    conn = db.connect()
    with conn:
        conn.execute("DELETE FROM documents WHERE public_id = ?", (doc["id"],))
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    conn.close()


def test_v2_database_is_migrated_not_refused(tmp_path, monkeypatch):
    path = tmp_path / "v2.db"
    old = sqlite3.connect(path)
    old.executescript(db.SCHEMA.replace(db.CHUNKS_SCHEMA, ""))  # the Day 7-10 schema
    old.execute("INSERT INTO documents (public_id, title, filename, stored_name, created_at) VALUES ('p', 't', 'f', 's', 'c')")
    old.execute("PRAGMA user_version = 2")
    old.commit()
    old.close()
    monkeypatch.setattr(settings, "db_path", path)
    db.init_db()
    conn = db.connect()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0  # table exists
    assert conn.execute("SELECT public_id FROM documents").fetchone()[0] == "p"  # data kept
    conn.close()


@pytest.mark.slow
def test_real_model_finds_the_us_growth_sentence():
    from app.services.embeddings import Embedder
    from app.services.extractor import extract
    from app.services.splitter import split

    sentences = split(extract(FIXTURES / "sample.docx"))
    db.init_db()
    conn = db.connect()
    pk = db.get_doc_pk(conn, db.insert_document(conn, "s", "s.docx", "s.docx", sentences))
    hits = retrieve(conn, pk, "How much did the U.S. grow?", Embedder(), k=4)
    conn.close()
    assert "3.5%" in hits[0].text
    # No absolute threshold here: a chunk mixes topics, so its score is diluted (~0.17
    # here vs ~0.69 for the bare sentence). Day 13's threshold comes from the eval data.
    assert hits[0].score > 2 * hits[1].score
