from types import SimpleNamespace

import numpy as np
import pytest

from app.services import audio_cache
from app.services.audio_cache import cache_key, canonical_voice
from app.services.timings import timings_from_results


def test_speed_formatting_shares_key():
    assert cache_key("Hi.", "af_heart", 1) == cache_key("Hi.", "af_heart", 1.0) == cache_key("Hi.", "af_heart", 1.00)
    assert cache_key("Hi.", "af_heart", 1) != cache_key("Hi.", "af_heart", 1.05)


def test_text_normalization_shares_key():
    # "e" + combining acute (NFD) vs precomposed "é" (NFC), plus messy whitespace
    assert cache_key("  Café  au\n lait ", "af_heart", 1) == cache_key("Café au lait", "af_heart", 1)


def test_blend_order_and_weight_scale_share_key():
    a = canonical_voice({"af_heart": 0.7, "am_michael": 0.3})
    b = canonical_voice({"am_michael": 3, "af_heart": 7})
    assert a == b == "af_heart:0.70+am_michael:0.30"
    assert canonical_voice("af_heart,af_bella") == canonical_voice({"af_bella": 1, "af_heart": 1})
    assert canonical_voice({"af_heart": 1.0}) == "af_heart"


def test_put_get_roundtrip_and_missing_sidecar(tmp_path):
    key = cache_key("Hello.", "af_heart", 1)
    assert audio_cache.get(key, tmp_path) is None

    timings = [{"word": "Hello.", "start": 0.1, "end": 0.5}]
    wav = audio_cache.put(key, np.zeros(2400, dtype=np.float32), timings, tmp_path)
    assert audio_cache.get(key, tmp_path) == (wav, timings)
    assert not list(tmp_path.glob("*.tmp"))

    (tmp_path / f"{key}.json").unlink()
    assert audio_cache.get(key, tmp_path) is None


@pytest.mark.parametrize("sidecar", ['{"version": "v1"}', "[1, 2]", '{"version": "v0", "timings": []}', "{not json"])
def test_malformed_sidecar_is_a_miss(tmp_path, sidecar):
    key = cache_key("Hello.", "af_heart", 1)
    audio_cache.put(key, np.zeros(10, dtype=np.float32), [], tmp_path)
    (tmp_path / f"{key}.json").write_text(sidecar, encoding="utf-8")
    assert audio_cache.get(key, tmp_path) is None


def test_version_bump_turns_old_entries_into_misses(tmp_path, monkeypatch):
    key_v2 = cache_key("Hello.", "af_heart", 1)
    monkeypatch.setattr(audio_cache, "CACHE_VERSION", "v1")
    key_v1 = cache_key("Hello.", "af_heart", 1)
    audio_cache.put(key_v1, np.zeros(10, dtype=np.float32), [], tmp_path)  # an entry written by old code
    monkeypatch.undo()
    assert key_v1 != key_v2 and audio_cache.get(key_v2, tmp_path) is None


def test_rejects_bad_keys(tmp_path):
    with pytest.raises(ValueError):
        audio_cache.get("../../etc/passwd", tmp_path)


def _tok(text, start, end, ws=" "):
    return SimpleNamespace(text=text, start_ts=start, end_ts=end, whitespace=ws)


def test_timings_attach_punctuation_and_offset_results():
    # Token shapes copied from real Kokoro output (scratch/token_probe.py)
    r1 = SimpleNamespace(audio=np.zeros(24000), tokens=[  # 1.0 s of audio
        _tok("said", 0.1, 0.2, ""), _tok(",", 0.2, 0.25), _tok('"', 0.25, 0.3, ""),
        _tok("Hello", 0.3, 0.5, ""), _tok("!", 0.5, 0.55, ""), _tok('"', 0.55, 0.6),
        _tok("costs", 0.6, 0.7), _tok("$", None, None, ""), _tok("5", 0.7, 0.8),
        _tok("--", None, None), _tok("v2.0", None, None, ""),  # untimed last word
    ])
    r2 = SimpleNamespace(audio=np.zeros(12000), tokens=[  # restarts at ~0
        _tok("#", None, None, ""), _tok("1", 0.1, 0.3, ""), _tok(".", 0.3, 0.35, ""),
    ])
    assert timings_from_results([r1, r2]) == [
        {"word": "said,", "start": 0.1, "end": 0.25},
        {"word": '"Hello!"', "start": 0.3, "end": 0.6},
        {"word": "costs", "start": 0.6, "end": 0.7},
        {"word": "$5 --", "start": 0.7, "end": 0.8},
        {"word": "v2.0", "start": 0.8, "end": 1.0},
        {"word": "#1.", "start": 1.1, "end": 1.35},
    ]


def test_timings_consecutive_untimed_words():
    r = SimpleNamespace(audio=np.zeros(24000), tokens=[
        _tok("Hi", 0.1, 0.2), _tok("v2.0", None, None), _tok("v3.0", None, None, ""),
    ])
    assert timings_from_results([r]) == [
        {"word": "Hi", "start": 0.1, "end": 0.2},
        {"word": "v2.0", "start": 0.2, "end": 0.2},
        {"word": "v3.0", "start": 0.2, "end": 1.0},
    ]


def test_timings_trailing_opening_punctuation_not_lost():
    r = SimpleNamespace(audio=np.zeros(2400), tokens=[_tok("Hi", 0.0, 0.1), _tok("(", None, None, "")])
    assert timings_from_results([r]) == [{"word": "Hi (", "start": 0.0, "end": 0.1}]
