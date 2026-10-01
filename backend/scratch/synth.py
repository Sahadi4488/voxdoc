"""Scratch synthesis helper (precursor to app/services/tts_engine.py on Day 5).

One KPipeline per lang_code, created lazily and reused; the 'b' pipeline
shares the 'a' pipeline's model weights instead of loading them twice.
"""
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from kokoro import KPipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

from app.services import audio_cache  # noqa: E402
from app.services.audio_cache import cache_key, normalize_text  # noqa: E402
from app.services.timings import timings_from_results  # noqa: E402
from app.services.voices import lang_code_for, validate_speed  # noqa: E402

REPO_ID = "hexgrad/Kokoro-82M"


@lru_cache(maxsize=None)
def get_pipeline(lang_code: str) -> KPipeline:
    model = get_pipeline("a").model if lang_code != "a" else True
    return KPipeline(lang_code=lang_code, repo_id=REPO_ID, model=model)


def resolve_voice(voice, pipeline: KPipeline):
    """A voice id string, or a {voice_id: weight} blend -> weighted voice tensor."""
    if isinstance(voice, str):
        return voice
    total = sum(voice.values())
    return sum((w / total) * pipeline.load_voice(v) for v, w in voice.items())


def synthesize(text: str, voice, speed: float = 1.0, lang_code: str | None = None):
    """Uncached synthesis -> (audio np.float32, timings)."""
    speed = validate_speed(speed)
    if lang_code is None:
        first = voice if isinstance(voice, str) else max(voice, key=voice.get)
        lang_code = lang_code_for(first)
    pipe = get_pipeline(lang_code)
    results = list(pipe(normalize_text(text), voice=resolve_voice(voice, pipe), speed=speed))
    audio = torch.cat([r.audio for r in results]).cpu().numpy().astype(np.float32)
    return audio, timings_from_results(results)


def speak(text: str, voice, speed: float = 1.0, cache_dir=None):
    """Cached synthesis -> (wav_path, timings, cache_hit)."""
    key = cache_key(text, voice, speed)
    hit = audio_cache.get(key, cache_dir)
    if hit:
        return (*hit, True)
    audio, timings = synthesize(text, voice, speed)
    return audio_cache.put(key, audio, timings, cache_dir), timings, False
