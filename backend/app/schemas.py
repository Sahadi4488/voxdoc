"""API response models."""
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str  # public_id: unguessable, never the internal integer key
    title: str
    filename: str
    sentence_count: int
    created_at: datetime


class SentenceOut(BaseModel):
    idx: int
    text: str
    page: int | None  # None for DOCX
    para: int


class DocumentDetail(DocumentOut):
    sentences: list[SentenceOut]


class ErrorOut(BaseModel):
    detail: str


class PresetOut(BaseModel):
    id: str
    name: str
    voice: str
    accent: str
    gender: str
    default_speed: float
    use: str
    description: str
    is_default: bool


class TTSRequest(BaseModel):
    doc_id: str = Field(description="The document's public id")
    sentence_idx: int = Field(ge=0)
    voice: str = Field(description="Preset id from GET /voices, e.g. 'presenter'")
    speed: float | None = Field(None, ge=0.5, le=2.0, description="Defaults to the preset's speed")


class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class TTSResponse(BaseModel):
    audio_url: str
    timings: list[WordTiming]
    duration: float
    cached: bool
