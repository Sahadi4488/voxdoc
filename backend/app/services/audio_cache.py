"""Hash-based disk cache for synthesized audio + word timings.

Each entry is two files in the cache directory:
    <key>.wav   24 kHz mono audio
    <key>.json  sidecar with word timings

The JSON is written last (both files via temp file + os.replace), so
"JSON exists" means the entry is complete. A missing or unreadable JSON is a miss.

No kokoro/torch imports here: audio arrives as a NumPy array.
"""
import hashlib
import json
import os
import re
import unicodedata
import uuid
from collections.abc import Mapping
from pathlib import Path

import soundfile as sf

from app.config import settings

CACHE_VERSION = "v2"  # bump when the audio or timing format changes (v2: timings carry char offsets)
SAMPLE_RATE = 24000
# Default directory is settings.audio_cache_dir, read at call time (never
# captured at import) so tests can point it at a temp folder.

_KEY_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize_text(text: str) -> str:
    """NFC-normalize, strip, and collapse whitespace runs (PDF text is messy).

    Use the same normalized text for synthesis so cached audio matches the key.
    """
    return " ".join(unicodedata.normalize("NFC", text).split())


def canonical_voice(voice: str | Mapping[str, float]) -> str:
    """Canonical voice string for cache keys.

    "af_heart"                          -> "af_heart"
    {"am_michael": 3, "af_heart": 7}    -> "af_heart:0.70+am_michael:0.30"
    "af_heart,af_bella" (Kokoro avg)    -> "af_bella:0.50+af_heart:0.50"
    Weights are normalized to sum to 1 and voices sorted, so A+B == B+A.
    """
    if isinstance(voice, str):
        names = [v.strip() for v in voice.split(",") if v.strip()]
        weights = {n: 1.0 for n in names}
    else:
        weights = {k.strip(): float(w) for k, w in voice.items() if float(w) > 0}
    if not weights:
        raise ValueError("Voice is empty.")
    if len(weights) == 1:
        return next(iter(weights))
    total = sum(weights.values())
    return "+".join(f"{v}:{w / total:.2f}" for v, w in sorted(weights.items()))


def cache_key(text: str, voice: str | Mapping[str, float], speed: float) -> str:
    # Text goes last: it is the only part that may contain "|".
    parts = [CACHE_VERSION, canonical_voice(voice), f"{float(speed):.2f}", normalize_text(text)]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _paths(key: str, cache_dir: Path | None) -> tuple[Path, Path]:
    if not _KEY_RE.match(key):
        raise ValueError(f"Invalid cache key {key!r}.")
    d = Path(cache_dir) if cache_dir else settings.audio_cache_dir
    return d / f"{key}.wav", d / f"{key}.json"


def get(key: str, cache_dir: Path | None = None) -> tuple[Path, list[dict]] | None:
    wav_path, json_path = _paths(key, cache_dir)
    try:
        sidecar = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # no sidecar (or corrupt) -> incomplete entry
    if (
        not isinstance(sidecar, dict)
        or sidecar.get("version") != CACHE_VERSION
        or not isinstance(sidecar.get("timings"), list)
        or not wav_path.exists()
    ):
        return None
    return wav_path, sidecar["timings"]


def put(key: str, audio, timings: list[dict], cache_dir: Path | None = None) -> Path:
    wav_path, json_path = _paths(key, cache_dir)
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    tmp = wav_path.with_name(f".{key}.{uuid.uuid4().hex}.tmp")
    try:
        sf.write(tmp, audio, SAMPLE_RATE, format="WAV")
        os.replace(tmp, wav_path)

        sidecar = {
            "version": CACHE_VERSION,
            "sample_rate": SAMPLE_RATE,
            "duration": len(audio) / SAMPLE_RATE,
            "timings": timings,
        }
        tmp.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, json_path)  # entry is complete only once this lands
    finally:
        tmp.unlink(missing_ok=True)
    return wav_path
