"""Document upload and library endpoints.

Routes are plain `def`: extraction and spaCy are blocking CPU work, so FastAPI
runs them in its threadpool instead of freezing the event loop.
"""
import re
import sqlite3
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile

from app import db
from app.config import settings
from app.schemas import DocumentDetail, DocumentOut, ErrorOut
from app.services.embeddings import Embedder, get_embedder
from app.services.extractor import NoTextError, UnreadableFileError, extract
from app.services.indexer import index_document
from app.services.splitter import split

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".docx"}
CHUNK = 1024 * 1024


@router.post(
    "",  # not "/": with the prefix that would be /documents/ and POST /documents would 307
    status_code=201,
    response_model=DocumentOut,
    responses={code: {"model": ErrorOut} for code in (400, 413, 415, 422)},
)
def upload_document(file: UploadFile, background_tasks: BackgroundTasks,
                    conn: sqlite3.Connection = Depends(db.get_db),
                    embedder: Embedder = Depends(get_embedder)):
    filename = _basename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"Unsupported file type {suffix or '(none)'}. Upload a .pdf or .docx file.")

    # Never use the client's filename as a path (../../ traversal); it's display-only.
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored = settings.upload_dir / stored_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        size = _save_limited(file.file, stored, settings.max_upload_bytes)
        if size == 0:
            raise HTTPException(400, "The uploaded file is empty.")
        try:
            pages = extract(stored)
        except NoTextError:
            raise HTTPException(422, "This PDF has no selectable text, so it's probably a scan. "
                                     "VoxDoc can't read scans.") from None
        except UnreadableFileError as e:
            raise HTTPException(422, str(e).replace(stored_name, filename)) from None
        if len(pages) > settings.max_pages:  # checked before splitting: don't spend the CPU
            raise HTTPException(413, f"This document has {len(pages)} pages. "
                                     f"VoxDoc reads up to {settings.max_pages}.")
        sentences = split(pages)
        if not sentences:
            raise HTTPException(422, "No readable sentences found in this document.")
        if len(sentences) > settings.max_sentences:
            raise HTTPException(413, f"This document has {len(sentences)} sentences. "
                                     f"VoxDoc reads up to {settings.max_sentences}.")
        public_id = db.insert_document(conn, Path(filename).stem or "Untitled", filename, stored_name, sentences)
    except BaseException:
        stored.unlink(missing_ok=True)  # no orphan files; the DB transaction already rolled back
        raise
    if settings.index_on_upload:
        # Runs after the response is sent; retrieval re-checks, so a failure here self-heals
        background_tasks.add_task(index_document, public_id, embedder)
    return db.get_document(conn, public_id, with_sentences=False)


# No GET /documents list: on a public server it would show everyone's uploads.
# A document is reachable only by its unguessable public_id (a private share link).


@router.get("/{public_id}", response_model=DocumentDetail, responses={404: {"model": ErrorOut}})
def get_document(public_id: str, conn: sqlite3.Connection = Depends(db.get_db)):
    doc = db.get_document(conn, public_id)
    if doc is None:
        raise HTTPException(404, "Document not found. Check the link, or upload the file again.")
    return doc


def _basename(name: str | None) -> str:
    """Client filename without any directory part (browsers may send C:\\fakepath\\x.pdf)."""
    return re.split(r"[\\/]", name or "")[-1].strip()


def _save_limited(src: BinaryIO, dest: Path, max_bytes: int) -> int:
    """Copy in chunks, stopping with 413 as soon as the size limit is passed."""
    size = 0
    with dest.open("wb") as out:
        while chunk := src.read(CHUNK):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(413, f"File too large: the limit is {max_bytes // (1024 * 1024)} MB.")
            out.write(chunk)
    return size
