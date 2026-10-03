"""Hash-based disk cache for synthesized audio + word timings.

Each entry is two files in the cache directory:
    <key>.wav   24 kHz mono audio
    <key>.json  sidecar with word timings

The JSON is written last (both files via temp file + os.replace), so
"JSON exists" means the entry is complete. A missing or unreadable JSON is a miss.

The cache is capped (settings.audio_cache_max_mb): prune_cache() runs at
startup and every PRUNE_EVERY writes and deletes the least recently used
entries. A hit refreshes the sidecar's modification time, so "oldest mtime"
means "least recently used".

No kokoro/torch imports here: audio arrives as a NumPy array.
"""
import hashlib
import json
import os
import re
import threading
import time
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

PRUNE_EVERY = 50  # writes between automatic prunes
PRUNE_TO = 0.8  # prune down to 80% of the cap, so the next write doesn't prune again
STALE_TMP_S = 3600  # a temp file this old belongs to a write that crashed

_writes = 0
_writes_lock = threading.Lock()


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
    try:
        os.utime(json_path)  # recently used: pruning removes the least recently used first
    except OSError:
        pass
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
    _count_write(cache_dir)
    return wav_path


def _count_write(cache_dir: Path | None) -> None:
    global _writes
    with _writes_lock:
        _writes += 1
        due = _writes % PRUNE_EVERY == 0
    if due:
        prune_cache(settings.audio_cache_max_bytes, cache_dir)


def prune_cache(max_bytes: int, cache_dir: Path | None = None) -> int:
    """If the cache is over max_bytes, delete the least recently used entries until
    it's under PRUNE_TO of it. Returns the bytes freed.

    Each entry's sidecar goes BEFORE its WAV: "JSON exists" means "complete", so a
    sidecar left without its WAV would be served as a hit, and the audio would 404.
    A WAV without a sidecar (a write that crashed) is garbage and goes first.
    """
    d = Path(cache_dir) if cache_dir else settings.audio_cache_dir
    if not d.is_dir():
        return 0
    entries: dict[str, list] = {}  # key -> [last used or None, size, files]
    total = 0
    now = time.time()
    for f in d.iterdir():
        try:
            st = f.stat()
        except OSError:
            continue  # deleted meanwhile
        if not f.is_file():
            continue
        total += st.st_size
        if f.name.startswith("."):  # a write in progress (".<key>.<uuid>.tmp")
            if now - st.st_mtime > STALE_TMP_S:
                f.unlink(missing_ok=True)
            continue
        entry = entries.setdefault(f.stem, [None, 0, []])
        entry[1] += st.st_size
        entry[2].append(f)
        if f.suffix == ".json":
            entry[0] = st.st_mtime
    if total <= max_bytes:
        return 0

    freed = 0
    # Entries without a sidecar first, then by last use, oldest first
    for _, size, files in sorted(entries.values(), key=lambda e: (e[0] is not None, e[0] or 0)):
        if total - freed <= max_bytes * PRUNE_TO:
            break
        for f in sorted(files, key=lambda f: f.suffix != ".json"):  # the sidecar first
            f.unlink(missing_ok=True)
        freed += size
    return freed
