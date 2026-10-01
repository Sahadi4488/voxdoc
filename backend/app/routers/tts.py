"""Text-to-speech endpoints.

The API speaks in preset ids, never Kokoro voice ids: the frontend doesn't know
Kokoro exists, so the engine can be swapped without touching React.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.schemas import ErrorOut, PresetOut, TTSRequest, TTSResponse
from app.services.tts_engine import SynthesisError, TTSEngine, get_or_create_audio, get_tts_engine
from app.services.voices import get_preset, list_presets

router = APIRouter(tags=["tts"])


@router.get("/voices", response_model=list[PresetOut])
def voices():
    return list_presets()


@router.post("/tts", response_model=TTSResponse, responses={404: {"model": ErrorOut}, 422: {"model": ErrorOut}})
def tts(req: TTSRequest, conn: sqlite3.Connection = Depends(db.get_db),
        engine: TTSEngine = Depends(get_tts_engine)):
    # Plain `def`: synthesis blocks for seconds, so it must run in the threadpool.
    text = db.get_sentence_text(conn, req.doc_id, req.sentence_idx)
    if text is None:
        doc = db.get_document(conn, req.doc_id, with_sentences=False)
        if doc is None:
            raise HTTPException(404, "Document not found.")
        raise HTTPException(404, f"Sentence {req.sentence_idx} not found: the document "
                                 f"has sentences 0-{doc['sentence_count'] - 1}.")
    try:
        preset = get_preset(req.voice)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    speed = req.speed if req.speed is not None else preset.default_speed

    try:
        result = get_or_create_audio(engine, text, preset.voice, speed)
    except SynthesisError as e:
        raise HTTPException(422, str(e)) from None
    return TTSResponse(audio_url=f"/audio/{result.key}.wav", timings=result.timings,
                       duration=round(result.duration, 3), cached=result.cached)
