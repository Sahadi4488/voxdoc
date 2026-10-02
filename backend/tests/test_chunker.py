import random

import pytest

from app.services.chunker import MAX_TOKENS, chunk
from app.services.splitter import Sentence


def words(n, tag="w"):
    return " ".join(f"{tag}{i}" for i in range(n))


def sents(spec):
    """spec: list of (word_count, para) -> Sentences."""
    return [Sentence(i, words(n, f"s{i}x"), None, para) for i, (n, para) in enumerate(spec)]


def count(text):  # 1 token per word + [CLS]/[SEP]: makes sizes exact in tests
    return len(text.split()) + 2


def assert_invariants(sentences, chunks, limit=MAX_TOKENS):
    assert chunks, "non-empty input must give chunks"
    assert [c.idx for c in chunks] == list(range(len(chunks)))
    covered = set()
    for c in chunks:
        covered.update(range(c.start_idx, c.end_idx + 1))
        assert c.text == " ".join(s.text for s in sentences[c.start_idx:c.end_idx + 1])  # consecutive sentences
        if c.end_idx > c.start_idx:  # multi-sentence chunks respect the limit
            assert count(c.text) <= limit
    assert covered == {s.idx for s in sentences}
    for a, b in zip(chunks, chunks[1:]):
        assert b.start_idx > a.start_idx  # the window always moves: no infinite loop
        assert b.start_idx in (a.end_idx, a.end_idx + 1)  # one-sentence overlap (or none, when it can't fit)


def test_overlap_by_one_sentence():
    s = sents([(30, 0)] * 20)
    c = chunk(s, count, target=100, limit=256)
    assert_invariants(s, c)
    assert all(b.start_idx == a.end_idx for a, b in zip(c, c[1:]))
    assert all(len(x.text.split()) <= 130 for x in c)


def test_single_sentence_document():
    s = sents([(5, 0)])
    assert [(c.start_idx, c.end_idx) for c in chunk(s, count)] == [(0, 0)]


def test_one_giant_sentence_is_its_own_chunk():
    s = sents([(10, 0), (400, 0), (10, 0), (10, 0)])
    c = chunk(s, count)
    assert_invariants(s, c)
    assert (1, 1) in [(x.start_idx, x.end_idx) for x in c]
    assert not any(x.start_idx <= 1 <= x.end_idx and x.start_idx != x.end_idx for x in c)


def test_only_giant_sentences():
    s = sents([(300, 0)] * 3)
    assert [(c.start_idx, c.end_idx) for c in chunk(s, count)] == [(0, 0), (1, 1), (2, 2)]


def test_many_tiny_sentences_terminate():
    s = sents([(1, i // 3) for i in range(2000)])
    assert_invariants(s, chunk(s, count))


def test_prefers_paragraph_boundaries():
    # target 100: paragraph 0 has 60 tokens (>= half the target), so the chunk closes there
    s = sents([(30, 0), (30, 0), (30, 1), (30, 1), (30, 1)])
    c = chunk(s, count, target=100, limit=256)
    assert (c[0].start_idx, c[0].end_idx) == (0, 1)


def test_no_early_close_for_a_short_paragraph():
    s = sents([(5, 0), (30, 1), (30, 1)])  # a heading-sized paragraph stays with what follows
    c = chunk(s, count, target=100, limit=256)
    assert (c[0].start_idx, c[0].end_idx) == (0, 2)


def test_empty():
    assert chunk([], count) == []


@pytest.mark.parametrize("seed", range(30))
def test_random_documents_keep_the_invariants(seed):
    rng = random.Random(seed)
    para, spec = 0, []
    for _ in range(rng.randint(1, 120)):
        para += rng.random() < 0.25
        spec.append((rng.choice([1, 3, 8, 20, 40, 90, 260]), para))
    s = sents(spec)
    assert_invariants(s, chunk(s, count))


@pytest.mark.slow
def test_real_tokenizer_no_chunk_exceeds_the_model_limit():
    from app.services.embeddings import Embedder
    from app.services.extractor import extract
    from app.services.splitter import split
    from tests.conftest import FIXTURES

    e = Embedder()
    technical = "We report 41.8 BLEU [38, 24, 15] with h_t−1 = W·x + b (Eq. 3) on WMT-2014 En→De; p < 0.01."
    docs = [split(extract(FIXTURES / "sample.pdf")), split(extract(FIXTURES / "sample.docx")),
            [Sentence(i, technical, None, 0) for i in range(60)]]
    for s in docs:
        c = chunk(s, e.count_tokens, limit=e.max_tokens)
        assert_invariants(s, c, limit=e.max_tokens)
        assert max(e.count_tokens(x.text) for x in c) <= e.max_tokens
