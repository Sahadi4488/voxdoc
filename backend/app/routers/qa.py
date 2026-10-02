"""Questions about a document (Day 13): grounded answers with sentence citations.

Order: rate limit (a dependency, so it runs before the body is validated:
every request counts), validate, then retrieve, threshold, LLM, parse.
LLM failures become 429/502/503/504 in main.py, as for summaries.
"""
import math
import sqlite3
from dataclasses import asdict
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request

from app import db
from app.config import settings
from app.schemas import AnswerOut, AskRequest, ErrorOut
from app.services.embeddings import Embedder, get_embedder
from app.services.llm import LLMClient, get_llm_client
from app.services.qa import answer_question
from app.utils.rate_limit import RateLimited, SlidingWindowLimiter

router = APIRouter(prefix="/documents", tags=["ai"])


@lru_cache(maxsize=1)
def get_question_limiter() -> SlidingWindowLimiter:
    """Process-wide; a dependency, so tests can swap in one with a fake clock."""
    return SlidingWindowLimiter(settings.qa_rate_limit, settings.qa_rate_window_s)


def limit_questions(request: Request, limiter: SlidingWindowLimiter = Depends(get_question_limiter)) -> None:
    # Keyed by IP address. Behind a reverse proxy this is the proxy's address, so
    # every visitor would share one bucket: Day 14 runs uvicorn with --proxy-headers
    # (only behind a proxy we trust, since the header can be forged otherwise).
    key = request.client.host if request.client else "unknown"
    allowed, retry_after = limiter.check(key)
    if not allowed:
        minutes = math.ceil(retry_after / 60)
        raise RateLimited(retry_after, f"You've asked a lot of questions. Try again in "
                                       f"{minutes} minute{'' if minutes == 1 else 's'}.")


@router.post("/{public_id}/ask", response_model=AnswerOut, dependencies=[Depends(limit_questions)],
             responses={code: {"model": ErrorOut} for code in (404, 422, 429, 502, 503, 504)})
def ask(public_id: str, body: AskRequest, conn: sqlite3.Connection = Depends(db.get_db),
        llm: LLMClient = Depends(get_llm_client), embedder: Embedder = Depends(get_embedder)):
    # Plain `def`: embedding the question and waiting on Groq block, so it runs in the threadpool
    doc_pk = db.get_doc_pk(conn, public_id)
    if doc_pk is None:
        raise HTTPException(404, "Document not found. Check the link, or upload the file again.")
    return AnswerOut(**asdict(answer_question(conn, doc_pk, body.question, llm, embedder)))
