from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import app
from tests.conftest import FIXTURES, upload


def uploads(tmp_path):
    d = tmp_path / "uploads"
    return list(d.iterdir()) if d.exists() else []


def row_count(table):
    conn = db.connect()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # table name is a test constant
    finally:
        conn.close()


def test_upload_docx_and_fetch(client, tmp_path):
    r = upload(client, FIXTURES / "sample.docx")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "sample" and body["filename"] == "sample.docx"
    assert body["sentence_count"] == 17  # same as scratch/split_demo.py
    assert len(uploads(tmp_path)) == 1

    detail = client.get(f"/documents/{body['id']}").json()
    assert [s["idx"] for s in detail["sentences"]] == list(range(17))
    assert {s["page"] for s in detail["sentences"]} == {None}
    assert detail["sentences"][0]["para"] == 0 and detail["sentences"][-1]["para"] > 0


def test_upload_pdf_pages(client):
    r = upload(client, FIXTURES / "sample.pdf")
    assert r.status_code == 201, r.text
    sents = client.get(f"/documents/{r.json()['id']}").json()["sentences"]
    assert len(sents) == 39
    s = next(s for s in sents if "needs for highlighting" in s["text"])
    assert s["page"] == 1
    assert sents[-1]["page"] == 2


def test_public_ids_are_unguessable(client):
    ids = [upload(client, FIXTURES / "sample.docx").json()["id"] for _ in range(3)]
    assert len(set(ids)) == 3
    assert all(isinstance(i, str) and len(i) >= 11 and not i.isdigit() for i in ids)
    for internal in ("1", "2", "3"):  # counting doesn't reach anyone's documents
        assert client.get(f"/documents/{internal}").status_code == 404


def test_no_public_document_list(client):
    upload(client, FIXTURES / "sample.docx")
    assert client.get("/documents").status_code == 405  # POST only


def test_data_survives_restart(client):
    doc_id = upload(client, FIXTURES / "sample.docx").json()["id"]
    with TestClient(app) as again:  # new lifespan, same db_path
        assert again.get(f"/documents/{doc_id}").status_code == 200


@pytest.mark.parametrize("name,content,status", [
    ("notes.txt", b"hello", 415),
    ("noextension", b"hello", 415),
    ("empty.pdf", b"", 400),
    ("fake.pdf", b"not really a pdf", 422),
    ("fake.docx", b"not really a docx", 422),
])
def test_rejected_uploads_leave_nothing(client, tmp_path, name, content, status):
    r = upload(client, name=name, content=content)
    assert r.status_code == status
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]
    assert row_count("documents") == 0 and row_count("sentences") == 0
    assert uploads(tmp_path) == []


def test_scanned_pdf_is_422(client, tmp_path):
    r = upload(client, FIXTURES / "scanned.pdf")
    assert r.status_code == 422
    assert "probably a scan" in r.json()["detail"]
    assert row_count("documents") == 0 and uploads(tmp_path) == []


def test_too_large_is_413(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)  # every non-empty file is too big
    r = upload(client, FIXTURES / "sample.docx")
    assert r.status_code == 413 and "too large" in r.json()["detail"]
    assert uploads(tmp_path) == []


def test_path_traversal_filename_is_harmless(client, tmp_path):
    r = upload(client, FIXTURES / "sample.docx", name="../../evil.docx")
    assert r.status_code == 201
    assert r.json()["filename"] == "evil.docx"
    assert not (tmp_path / "evil.docx").exists() and not (tmp_path.parent / "evil.docx").exists()
    assert len(uploads(tmp_path)) == 1


@pytest.mark.parametrize("cap,value,expected", [("max_pages", 2, "has 3 pages"), ("max_sentences", 10, "has 39 sentences")])
def test_upload_caps_413(client, tmp_path, monkeypatch, cap, value, expected):
    monkeypatch.setattr(settings, cap, value)
    r = upload(client, FIXTURES / "sample.pdf")
    assert r.status_code == 413 and expected in r.json()["detail"]
    assert row_count("documents") == 0 and uploads(tmp_path) == []


def test_db_failure_leaves_no_file(client, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("disk full")
    monkeypatch.setattr(db, "insert_document", boom)
    with pytest.raises(RuntimeError):
        upload(client, FIXTURES / "sample.docx")
    assert uploads(tmp_path) == []


def test_unknown_id_is_404(client):
    r = client.get("/documents/not-a-real-id")
    assert r.status_code == 404 and "Document not found" in r.json()["detail"]


def test_cascade_delete(client):
    public_id = upload(client, FIXTURES / "sample.docx").json()["id"]
    assert row_count("sentences") == 17
    conn = db.connect()
    with conn:
        assert conn.execute("DELETE FROM documents WHERE public_id = ?", (public_id,)).rowcount == 1
    conn.close()
    assert row_count("sentences") == 0


def test_old_schema_refuses_to_start(tmp_path, monkeypatch):
    import sqlite3
    old = tmp_path / "old.db"
    sqlite3.connect(old).executescript("CREATE TABLE documents (id INTEGER PRIMARY KEY);")
    monkeypatch.setattr(settings, "db_path", old)
    with pytest.raises(db.SchemaMismatchError, match="delete it"):
        db.init_db()
