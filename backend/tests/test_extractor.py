from pathlib import Path

import pytest

from app.services.extractor import NoTextError, Page, dehyphenate, extract

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def pdf_pages():
    return extract(FIXTURES / "sample.pdf")


@pytest.fixture(scope="module")
def docx_pages():
    return extract(FIXTURES / "sample.docx")


def test_pdf_pages_numbered(pdf_pages):
    assert [p.number for p in pdf_pages] == [1, 2, 3]


def test_pdf_clean_text(pdf_pages):
    text = "\n\n".join(p.text for p in pdf_pages)
    assert "\n\n\n" not in text and all("\n" not in para for para in text.split("\n\n"))
    assert "Fixture Paper" not in text  # running header removed
    assert "•" not in text
    assert "commercial" in text and "typesetting" in text  # de-hyphenated
    assert "text-to-speech" in text and "state-of-the-art" in text  # compounds kept


def test_pdf_page_numbers_dropped(pdf_pages):
    for p in pdf_pages:
        assert all(not para.isdigit() for para in p.text.split("\n\n"))


def test_pdf_headings_are_paragraphs(pdf_pages):
    paras = pdf_pages[0].text.split("\n\n")
    assert "1. Introduction" in paras and "2.1 Synthesis" in paras


def test_pdf_page_continuation(pdf_pages):
    assert pdf_pages[0].continues and pdf_pages[0].text.endswith("high-")
    assert pdf_pages[1].continues  # sentence carries on to page 3
    assert not pdf_pages[2].continues


def test_docx(docx_pages):
    assert len(docx_pages) == 1 and docx_pages[0].number is None
    paras = docx_pages[0].text.split("\n\n")
    assert paras[0] == "VoxDoc Test Document"
    assert "Extract the text." in paras  # bullet items are separate paragraphs
    assert "soft line break in the middle" in docx_pages[0].text
    assert "ﬁ" not in docx_pages[0].text and "This file" in docx_pages[0].text  # NFKC ligature
    assert "af_heart" not in docx_pages[0].text  # table skipped


def test_unsupported_extension(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    with pytest.raises(ValueError, match="Unsupported"):
        extract(f)


def test_scanned_pdf_raises():
    with pytest.raises(NoTextError):
        extract(FIXTURES / "scanned.pdf")


@pytest.mark.parametrize("raw,clean", [
    ("commer-\ncial", "commercial"),
    ("state-of-\nthe-art", "state-of-the-art"),
    ("English-\nto-German", "English-to-German"),
    ("mid-\nrange", "midrange"),  # documented trade-off
    ("pages 3-\n5", "pages 35"),  # digits are \w too; rare enough to accept
    ("end -\nstart", "end -\nstart"),  # spaced dash is not a hyphenation
])
def test_dehyphenate(raw, clean):
    assert dehyphenate(raw) == clean


def test_page_is_frozen():
    with pytest.raises(AttributeError):
        Page(1, "x").text = "y"
