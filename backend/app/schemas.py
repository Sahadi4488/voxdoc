"""API response models."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


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
    # Where the word sits in the sentence text, as JavaScript (UTF-16) string
    # indices; None if it couldn't be aligned
    char_start: int | None = None
    char_end: int | None = None


class TTSResponse(BaseModel):
    audio_url: str
    timings: list[WordTiming]
    duration: float
    cached: bool


class SummaryOut(BaseModel):
    overview: str
    key_points: list[str]
    # "excerpts": a long document, summarised from selected passages (the UI says so)
    source: Literal["full", "excerpts"]
    model: str
    created_at: datetime
    cached: bool


class AskRequest(BaseModel):
    # Whitespace is stripped first, so "   " is too short: 422
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class TextPart(BaseModel):
    text: str


class CitePart(BaseModel):
    cite: int = Field(description="Global sentence idx, as in DocumentDetail.sentences")


class AnswerOut(BaseModel):
    parts: list[TextPart | CitePart] = Field(description="The answer in reading order: text and citation chips")
    citations: list[int] = Field(description="Sorted, unique sentence indices cited")
    found: bool = Field(description="False: the document doesn't answer the question")
    grounded: bool = Field(description="found, and at least one citation is of a sentence the model was shown")
