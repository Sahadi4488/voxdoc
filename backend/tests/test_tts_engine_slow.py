"""Real Kokoro. Skipped by default; run with:  pytest -m slow"""
import pytest

from app.services.tts_engine import TTSEngine, get_or_create_audio

pytestmark = pytest.mark.slow

SENTENCE = ("The reader synthesizes each sentence on its own, so the listener hears "
            "the first words within about a second of pressing play.")


@pytest.fixture(scope="module")
def engine():
    return TTSEngine()


def test_timings_end_near_duration(engine):
    audio, timings = engine.synthesize(SENTENCE, "af_heart", 1.0)
    duration = len(audio) / 24000
    assert audio.dtype.name == "float32" and duration > 2
    assert len(timings) == len(SENTENCE.split())
    assert abs(timings[-1]["end"] - duration) <= 0.3
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(timings, timings[1:]))
    # every word aligned, and the spans spell out the sentence's words
    assert all(t["char_start"] is not None for t in timings)
    assert [SENTENCE[t["char_start"]:t["char_end"]] for t in timings] == SENTENCE.split()


def test_multi_chunk_timings_are_offset(engine):
    long_text = " ".join([SENTENCE] * 6)  # long enough for Kokoro to split internally
    audio, timings = engine.synthesize(long_text, "af_heart", 1.0)
    assert abs(timings[-1]["end"] - len(audio) / 24000) <= 0.3


def test_both_accents_share_one_model(engine):
    assert engine.pipeline("b").model is engine.pipeline("a").model
    audio, timings = engine.synthesize("Good morning, how are you?", "bm_george", 1.0)
    assert len(audio) > 0 and timings


def test_cached_round_trip(engine):
    first = get_or_create_audio(engine, SENTENCE, "am_michael", 1.0)
    second = get_or_create_audio(engine, SENTENCE, "am_michael", 1.0)
    assert (first.cached, second.cached) == (False, True)
    assert second.timings == first.timings and abs(second.duration - first.duration) < 1e-3
