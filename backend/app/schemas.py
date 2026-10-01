"""API response models."""
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    filename: str
    sentence_count: int
    created_at: datetime


class SentenceOut(BaseModel):
    idx: int
    text: str
    page: int | None  # None for DOCX


class DocumentDetail(DocumentOut):
    sentences: list[SentenceOut]


class ErrorOut(BaseModel):
    detail: str
