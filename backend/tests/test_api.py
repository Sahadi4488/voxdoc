from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh database + upload folder per test; the real data/ is never touched."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    with TestClient(app) as c:  # `with` runs the lifespan (init_db)
        yield c


def upload(client, path=None, name=None, content=None):
    data = content if content is not None else Path(path).read_bytes()
    return client.post("/documents", files={"file": (name or Path(path).name, data)})


def uploads(tmp_path):
    d = tmp_path / "uploads"
    return list(d.iterdir()) if d.exists() else []


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


def test_upload_pdf_pages(client):
    r = upload(client, FIXTURES / "sample.pdf")
    assert r.status_code == 201, r.text
    sents = client.get(f"/documents/{r.json()['id']}").json()["sentences"]
    assert len(sents) == 39
    s = next(s for s in sents if "needs for highlighting" in s["text"])
    assert s["page"] == 1
    assert sents[-1]["page"] == 2


def test_list_newest_first(client):
    a = upload(client, FIXTURES / "sample.docx").json()["id"]
    b = upload(client, FIXTURES / "sample.pdf").json()["id"]
    assert [d["id"] for d in client.get("/documents").json()] == [b, a]


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
    assert client.get("/documents").json() == []
    assert uploads(tmp_path) == []


def test_scanned_pdf_is_422(client, tmp_path):
    r = upload(client, FIXTURES / "scanned.pdf")
    assert r.status_code == 422
    assert "scanned" in r.json()["detail"]
    assert client.get("/documents").json() == [] and uploads(tmp_path) == []


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


def test_db_failure_leaves_no_file(client, tmp_path, monkeypatch):
    from app import db

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")
    monkeypatch.setattr(db, "insert_document", boom)
    with pytest.raises(RuntimeError):
        upload(client, FIXTURES / "sample.docx")
    assert uploads(tmp_path) == []


def test_unknown_id_is_404(client):
    r = client.get("/documents/9999")
    assert r.status_code == 404 and r.json() == {"detail": "Document 9999 not found."}


def test_cascade_delete(client):
    from app import db

    doc_id = upload(client, FIXTURES / "sample.docx").json()["id"]
    conn = db.connect()
    with conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    assert conn.execute("SELECT COUNT(*) FROM sentences WHERE doc_id = ?", (doc_id,)).fetchone()[0] == 0
    conn.close()
