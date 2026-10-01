from pathlib import Path

import pytest

from app.services.extractor import Page, extract
from app.services.splitter import MAX_CHARS, _fix_paragraph, split

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pdf_sents():
    return split(extract(FIXTURES / "sample.pdf"))


@pytest.fixture(scope="module")
def docx_sents():
    return split(extract(FIXTURES / "sample.docx"))


def texts(sents):
    return [s.text for s in sents]


def test_idx_contiguous(pdf_sents, docx_sents):
    for sents in (pdf_sents, docx_sents):
        assert [s.idx for s in sents] == list(range(len(sents)))


def test_abbreviations_not_split(pdf_sents, docx_sents):
    abbrev = "Dr. Smith arrived at 3 p.m., e.g. this, The U.S. grew 3.5% in 2024."
    assert abbrev in texts(pdf_sents) and abbrev in texts(docx_sents)
    assert "Prof. Lee costs approx. 5 dollars vs. 6 dollars at the store." in texts(docx_sents)


def test_headings_stand_alone(pdf_sents, docx_sents):
    for h in ["1. Introduction", "2.1 Synthesis", "3. Results", "4. Conclusion"]:
        assert h in texts(pdf_sents)
    assert "A short list" in texts(docx_sents)


def test_clean_text(pdf_sents, docx_sents):
    for s in pdf_sents + docx_sents:
        assert "\n" not in s.text and "ﬁ" not in s.text and "- " not in s.text
        assert 0 < len(s.text) <= MAX_CHARS
        assert any(c.isalnum() for c in s.text)


def test_sentence_across_page_break_keeps_start_page(pdf_sents):
    s = next(s for s in pdf_sents if "needs for highlighting" in s.text)
    assert s.page == 1 and s.text.endswith("needs for highlighting.")
    s = next(s for s in pdf_sents if s.text.startswith("Future work"))
    assert s.page == 2 and s.text.endswith("into a new one.")
    assert pdf_sents[-1].page == 2  # page 3 holds only the tail of that sentence


def test_long_sentence_split_near_middle(docx_sents):
    parts = [s.text for s in docx_sents if "chapter" in s.text or "streams the first clip" in s.text]
    assert len(parts) == 2 and parts[0].endswith("voice and speed,")


def test_docx_page_is_none(docx_sents):
    assert {s.page for s in docx_sents} == {None}


def _spans(text, parts):
    """(start, end) spans for consecutive pieces of text, like spaCy returns."""
    out, pos = [], 0
    for p in parts:
        start = text.index(p, pos)
        out.append((start, start + len(p)))
        pos = start + len(p)
    return out


@pytest.mark.parametrize("parts,expected", [
    (["Steps follow.", "1.", "Open the file."], ["Steps follow.", "1. Open the file."]),
    (["a)", "Then read it.", "..."], ["a) Then read it."]),
    (["It costs approx.", "5 dollars."], ["It costs approx. 5 dollars."]),
    (["See Fig.", "3 for details."], ["See Fig. 3 for details."]),
    (["It rained.", "and then it stopped."], ["It rained. and then it stopped."]),
    (["Prior work exists", "[38, 24].", "Next."], ["Prior work exists [38, 24].", "Next."]),
    (["Done.", "!", "2."], ["Done."]),
])
def test_fix_paragraph_rules(parts, expected):
    text = " ".join(parts)
    assert [text[a:b] for a, b in _fix_paragraph(_spans(text, parts), text)] == expected


def test_paragraphs_are_hard_boundaries():
    sents = split([Page(1, "Results\n\nThe model works")])
    assert texts(sents) == ["Results", "The model works"]


def test_page_join_rules():
    pages = [Page(1, "It was a state-of-", True), Page(2, "the-art result and a commer-", True),
             Page(3, "cial one, continued", True), Page(4, ""), Page(5, "here. Done.")]
    sents = split(pages)
    assert texts(sents) == ["It was a state-of-the-art result and a commercial one, continued here.", "Done."]
    assert [s.page for s in sents] == [1, 5]


def test_heading_at_page_end_not_glued():
    sents = split([Page(1, "Intro text.\n\n2. Method", False), Page(2, "We did it.")])
    assert texts(sents) == ["Intro text.", "2. Method", "We did it."]


def test_unbreakable_long_text_is_hard_cut():
    url = "https://example.com/" + "a" * 800
    sents = split([Page(1, url)])
    assert all(len(s.text) <= MAX_CHARS for s in sents) and "".join(texts(sents)) == url
