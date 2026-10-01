"""Split extracted pages into TTS-ready sentences.

- Paragraphs ("\\n\\n") are hard boundaries: a sentence never spans two
  paragraphs, so headings stay on their own.
- Pages are joined before splitting, so a sentence that crosses a page break
  stays whole; it gets the page on which it starts.
- spaCy (already installed with Kokoro's G2P) finds sentence boundaries; a few
  rules fix its known misses and shape sentences for TTS.
"""
import bisect
import re
from dataclasses import dataclass
from functools import lru_cache

from app.services.extractor import Page

MAX_CHARS = 350

# Abbreviations that never end a sentence: spaCy sometimes splits after them
# ("It costs approx." | "5 dollars").
_NO_END_RE = re.compile(
    r"(?<![\w.])(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|Fig|Figs|Eq|Eqs|Sec|Vol|No|vs|approx|cf|e\.g|i\.e)\.$",
    re.IGNORECASE,
)
# A bare list marker: "1." "12)" "a)" "(b)" "iv." "•"
_LIST_MARKER_RE = re.compile(r"^(\(?(\d{1,3}|[a-zA-Z]|[ivxlc]{1,6})[.)]|[•*\-–])$")
_CUT_RE = re.compile(r"[;:,](?=\s)")


@dataclass(frozen=True)
class Sentence:
    idx: int
    text: str
    page: int | None


@lru_cache(maxsize=1)
def _nlp():
    import spacy  # imported lazily: slow, and only needed here

    return spacy.load("en_core_web_sm", exclude=["ner", "lemmatizer"])


def warm_up() -> None:
    """Load the spaCy model ahead of the first request."""
    _nlp()


def split(pages: list[Page], max_chars: int = MAX_CHARS) -> list[Sentence]:
    text, page_starts, page_numbers = _join_pages(pages)
    paragraphs = [(m.start(), m.group().replace("\n", " "))  # same length: offsets stay valid
                  for m in re.finditer(r"[^\n]+(?:\n[^\n]+)*", text)]

    spans: list[tuple[int, int]] = []  # absolute (start, end) offsets into `text`
    for (base, para), doc in zip(paragraphs, _nlp().pipe(p for _, p in paragraphs)):
        sents = [(base + s.start_char, base + s.end_char) for s in doc.sents]
        for start, end in _fix_paragraph(sents, text):
            spans.extend(_split_long(start, end, text, max_chars))

    sentences = []
    for start, end in spans:
        page = page_numbers[bisect.bisect_right(page_starts, start) - 1]
        sentences.append(Sentence(len(sentences), _clean(text[start:end]), page))
    return sentences


def _join_pages(pages: list[Page]) -> tuple[str, list[int], list[int | None]]:
    """One text for the whole document + each page's start offset.

    Pages are joined with "\\n\\n" (paragraph break), or with "\\n" (soft break,
    becomes a space) when the previous page's last paragraph continues. A word
    hyphenated across the page break is re-joined, with the same compound rule
    as extractor.dehyphenate.
    """
    text, starts, numbers = "", [], []
    prev = None
    for page in pages:
        if not page.text:
            continue
        sep = ""
        if prev is not None:
            sep = "\n\n"
            if prev.continues:
                sep = "\n"
                before = re.search(r"([\w-]*\w)-$", text)
                after = re.match(r"\w[\w-]*", page.text)
                if before and after:
                    sep = ""
                    if "-" not in before[1] + after[0]:
                        text = text[:-1]
        text += sep
        starts.append(len(text))
        numbers.append(page.number)
        text += page.text
        prev = page
    return text, starts, numbers


def _fix_paragraph(sents: list[tuple[int, int]], text: str) -> list[tuple[int, int]]:
    """Repair spaCy's boundaries inside one paragraph."""
    out: list[tuple[int, int]] = []
    for start, end in sents:
        s = _clean(text[start:end])
        if out:
            prev = _clean(text[out[-1][0]:out[-1][1]])
            # Not a real boundary: after a non-final abbreviation or a bare list
            # marker, or before a lowercase word or a "[12]" citation
            if _NO_END_RE.search(prev) or _LIST_MARKER_RE.match(prev) or s[:1].islower() or s[:1] == "[":
                out[-1] = (out[-1][0], end)  # merge into the previous sentence
                continue
        out.append((start, end))
    # Drop empty / punctuation-only fragments and stray trailing list markers
    return [(a, b) for a, b in out
            if any(c.isalnum() for c in text[a:b]) and not _LIST_MARKER_RE.match(_clean(text[a:b]))]


def _split_long(start: int, end: int, text: str, max_chars: int) -> list[tuple[int, int]]:
    """Split at the ; : or , nearest the middle (else a space, else hard) until all fit."""
    # Trim surrounding whitespace so lengths and offsets are exact
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end - start <= max_chars:
        return [(start, end)]
    chunk = text[start:end]
    mid = len(chunk) / 2
    cuts = [m.end() for m in _CUT_RE.finditer(chunk)] or [m.start() for m in re.finditer(r" ", chunk)]
    cut = min(cuts, key=lambda c: abs(c - mid)) if cuts else max_chars
    return _split_long(start, start + cut, text, max_chars) + _split_long(start + cut, end, text, max_chars)


def _clean(s: str) -> str:
    return " ".join(s.split())
