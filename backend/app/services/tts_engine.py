"""Kokoro TTS engine + cached audio generation.

kokoro/torch are imported lazily inside TTSEngine, so importing this module
(and the API) stays fast and tests can swap in a fake engine.
"""
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf

from app.services import audio_cache
from app.services.audio_cache import SAMPLE_RATE, cache_key, normalize_text
from app.services.timings import align, timings_from_results
from app.services.voices import KOKORO_REPO, lang_code_for
from app.utils.locks import KeyedLock

REPO_ID = KOKORO_REPO


class SynthesisError(RuntimeError):
    """Kokoro produced no audio for the text."""


class TTSEngine:
    """One shared KModel; one KPipeline per lang_code, created on first use.

    KPipeline(model=True) would load its own copy of the weights; passing the
    shared KModel keeps a single copy in RAM however many accents are used.
    """

    def __init__(self, repo_id: str = REPO_ID):
        self.repo_id = repo_id
        self._model = None
        self._pipelines: dict = {}
        self._load_lock = threading.Lock()
        # One synthesis saturates the CPU; running two in parallel gains nothing
        # and risks thread-safety bugs in the G2P layer.
        self._synth_lock = threading.Lock()

    def pipeline(self, lang_code: str):
        with self._load_lock:
            if lang_code not in self._pipelines:
                from kokoro import KModel, KPipeline

                if self._model is None:
                    self._model = KModel(repo_id=self.repo_id).to("cpu").eval()
                self._pipelines[lang_code] = KPipeline(lang_code=lang_code, repo_id=self.repo_id, model=self._model)
            return self._pipelines[lang_code]

    def warm_up(self) -> None:
        self.pipeline("a")

    @property
    def loaded(self) -> bool:
        """Whether Kokoro is in memory (GET /api/health reports it; it never loads it)."""
        return self._model is not None

    def synthesize(self, text: str, kokoro_voice: str, speed: float) -> tuple[np.ndarray, list[dict]]:
        """-> (float32 audio at 24 kHz, word timings offset across Kokoro's chunks and
        aligned to character offsets in `text`, which is what the frontend displays)."""
        pipe = self.pipeline(lang_code_for(kokoro_voice))
        with self._synth_lock:
            results = [r for r in pipe(normalize_text(text), voice=kokoro_voice, speed=speed) if r.audio is not None]
        if not results:
            raise SynthesisError(f"No audio produced for {text!r}.")
        audio = np.concatenate([r.audio.cpu().numpy() for r in results]).astype(np.float32)
        return audio, align(text, timings_from_results(results))


@lru_cache(maxsize=1)
def get_tts_engine() -> TTSEngine:
    """Process-wide singleton; also the FastAPI dependency tests override."""
    return TTSEngine()


@dataclass(frozen=True)
class AudioResult:
    key: str
    wav_path: Path
    timings: list[dict]
    duration: float
    cached: bool


_audio_locks = KeyedLock()


def get_or_create_audio(engine, text: str, kokoro_voice: str, speed: float) -> AudioResult:
    """Cache hit -> return at once. Miss -> lock this cache key, re-check, synthesize, store.

    The re-check under the lock (double-checked locking) means two concurrent
    requests for the same sentence (play + prefetch) synthesize it only once.
    A miss for another sentence doesn't wait on this lock (only on the engine
    itself, inside synthesize).
    """
    key = cache_key(text, kokoro_voice, speed)

    def create() -> AudioResult:
        audio, timings = engine.synthesize(text, kokoro_voice, speed)
        wav_path = audio_cache.put(key, audio, timings)
        return AudioResult(key, wav_path, timings, len(audio) / SAMPLE_RATE, cached=False)

    return _audio_locks.get_or_create(key, lambda: _cached(key), create)


def _cached(key: str) -> AudioResult | None:
    entry = audio_cache.get(key)
    if entry is None:
        return None
    wav_path, timings = entry
    try:
        duration = sf.info(str(wav_path)).duration
    except (OSError, RuntimeError):  # pruned between get() and here (soundfile raises RuntimeError)
        return None
    return AudioResult(key, wav_path, timings, duration, cached=True)
