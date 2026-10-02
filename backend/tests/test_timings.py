from types import SimpleNamespace

import numpy as np
import pytest

from app.services.timings import align, timings_from_results


def words(*ws):
    """Timings for these words, 0.2 s each (align only reads "word")."""
    return [{"word": w, "start": i * 0.2, "end": (i + 1) * 0.2} for i, w in enumerate(ws)]


def spans(text, timings):
    return [None if t["char_start"] is None else text[t["char_start"]:t["char_end"]] for t in align(text, timings)]


def assert_valid(text, aligned):
    """0 <= start < end <= len(text) and spans never overlap (for BMP-only text)."""
    prev_end = 0
    for t in aligned:
        if t["char_start"] is None:
            continue
        assert prev_end <= t["char_start"] < t["char_end"] <= len(text)
        prev_end = t["char_end"]


def test_contraction_as_one_token():  # what Kokoro's G2P produces today
    assert spans("I don't know.", words("I", "don't", "know.")) == ["I", "don't", "know."]


def test_contraction_split_like_spacy():  # "do" + "n't" both land inside "don't"
    text = "I don't know."
    aligned = align(text, words("I", "do", "n't", "know."))
    assert [text[t["char_start"]:t["char_end"]] for t in aligned] == ["I", "do", "n't", "know."]
    assert aligned[1]["char_end"] == aligned[2]["char_start"] == 4
    assert_valid(text, aligned)


def test_abbreviations_decimals_percent():
    text = "The U.S. grew 3.5% in 2024."
    tokens = words("The", "U.S.", "grew", "3.5", "%", "in", "2024", ".")
    assert spans(text, tokens) == ["The", "U.S.", "grew", "3.5", "%", "in", "2024", "."]
    assert_valid(text, align(text, tokens))


def test_repeated_words_get_different_spans():
    aligned = align("the the", words("the", "the"))
    assert [(t["char_start"], t["char_end"]) for t in aligned] == [(0, 3), (4, 7)]


def test_unmatched_token_does_not_derail_the_rest():
    text = "Alpha beta gamma delta."
    aligned = align(text, words("Alpha", "zzz", "beta", "gamma", "delta."))
    assert spans(text, words("Alpha", "zzz", "beta", "gamma", "delta.")) == ["Alpha", None, "beta", "gamma", "delta."]
    assert aligned[1]["start"] == 0.2 and aligned[1]["end"] == 0.4  # timing kept
    assert_valid(text, aligned)


def test_missed_short_word_does_not_latch_onto_a_far_duplicate():
    text = "Kokoro said ah, then read a long paragraph about many things and finally a word."
    tokens = words("Kokoro", "said", "uh,", "then", "read")  # "uh," is not in the text
    assert spans(text, tokens) == ["Kokoro", "said", None, "then", "read"]


def test_core_fallback_when_punctuation_differs():
    text = "He said “quoted” words."
    assert spans(text, words("He", "said", '"quoted"', "words.")) == ["He", "said", "quoted", "words."]


def test_real_kokoro_shapes():
    text = "Dr. Smith’s café is naïve — “quoted” and 'single' (really?) costs $5 & 20%... OK."
    tokens = words("Dr.", "Smith’s", "café", "is", "naïve —", "“quoted”", "and", "'single'",
                   "(really?)", "costs", "$5", "&", "20%...", "OK.")
    aligned = align(text, tokens)
    assert all(t["char_start"] is not None for t in aligned)
    assert_valid(text, aligned)


def test_offsets_are_utf16_like_javascript():
    text = "😀 hi 𝑥 there"  # both symbols are outside the BMP: 2 UTF-16 units each in JS
    aligned = align(text, words("😀", "hi", "𝑥", "there"))
    assert [(t["char_start"], t["char_end"]) for t in aligned] == [(0, 2), (3, 5), (6, 8), (9, 14)]


def test_empty_inputs():
    assert align("Hello.", []) == []
    assert spans("", words("x")) == [None]


def _tok(text, start, end, ws=" ", phonemes=None):
    return SimpleNamespace(text=text, start_ts=start, end_ts=end, whitespace=ws, phonemes=phonemes)


@pytest.mark.parametrize("symbol,phonemes", [("&", "ænd"), ("/", "slˈæʃ")])
def test_spoken_symbols_are_words(symbol, phonemes):
    r = SimpleNamespace(audio=np.zeros(24000), tokens=[
        _tok("A", 0.0, 0.2, phonemes="ˈA"), _tok(symbol, 0.2, 0.4, phonemes=phonemes),
        _tok("B", 0.4, 0.6, "", phonemes="bˈi"), _tok(".", 0.6, 0.65, "", phonemes="."),
    ])
    assert [t["word"] for t in timings_from_results([r])] == ["A", symbol, "B."]


def test_silent_symbols_still_attach():
    r = SimpleNamespace(audio=np.zeros(24000), tokens=[
        _tok("wait", 0.0, 0.3, phonemes="wˈAt"), _tok("—", 0.3, 0.35, phonemes="—"),
        _tok("go", 0.35, 0.6, "", phonemes="ɡˈO"),
    ])
    assert [t["word"] for t in timings_from_results([r])] == ["wait —", "go"]
