"""AI summary endpoint (Day 12).

LLM failures are raised as LLMError subclasses and answered by the handler in
main.py (429 + Retry-After, 502, 503, 504) with user-facing messages only.
"""
import sqlite3
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.schemas import ErrorOut, SummaryOut
from app.services.embeddings import Embedder, get_embedder
from app.services.llm import LLMClient, get_llm_client
from app.services.summarizer import get_or_create_summary

router = APIRouter(prefix="/documents", tags=["ai"])


@router.post("/{public_id}/summary", response_model=SummaryOut,
             responses={code: {"model": ErrorOut} for code in (404, 429, 502, 503, 504)})
def summarize(public_id: str, conn: sqlite3.Connection = Depends(db.get_db),
              llm: LLMClient = Depends(get_llm_client), embedder: Embedder = Depends(get_embedder)):
    # Plain `def`: it waits seconds on Groq (and maybe on indexing) in the threadpool.
    # POST, not GET: the first call spends quota and writes the cache.
    doc = db.get_document(conn, public_id, with_sentences=False)
    if doc is None:
        raise HTTPException(404, "Document not found. Check the link, or upload the file again.")
    summary = get_or_create_summary(conn, db.get_doc_pk(conn, public_id), doc["title"], llm, embedder)
    return SummaryOut(**asdict(summary))
