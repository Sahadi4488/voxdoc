"""Convert Kokoro pipeline results into word timings, and align them to the text.

Format: [{"word", "start", "end", "char_start", "char_end"}, ...]. Times are in
seconds from the start of the concatenated audio. char_start/char_end locate
the word in the sentence text as JavaScript string indices (UTF-16 code
units), or are None when the word couldn't be found.

Token policy (decided Day 2, the frontend depends on it):
- Every entry is something the voice says: it has a letter or digit ("don't",
  "3.5%"), or it is a symbol Kokoro pronounces as a word ("&" -> "and",
  "/" -> "slash"). Silent punctuation never stands alone. Kokoro times most
  punctuation (",", "?", ")") but returns None for tokens without phonemes
  ("$", "#", "--").
  * Opening marks - no space after, and a space (or nothing) before, e.g.
    '"', "(", "$", "#" - are prepended to the next word: '"Wait', "$5".
  * Everything else is appended to the previous word ("world!", "20%..."),
    extending that word's end to cover the punctuation's timing.
- A word token with None timestamps (Kokoro can drop the last word of a long
  chunk) starts at the previous word's end and ends at the next word's start,
  or at the end of its chunk.

Kokoro restarts timestamps at ~0 for every result it yields, so each result
is offset by the cumulative audio duration of the results before it.

Duck-typed on Kokoro's Result/MToken; no kokoro or torch import needed.
"""
SAMPLE_RATE = 24000
ALIGN_LOOKAHEAD = 40  # a word is searched for at most this far past the cursor


def _is_spoken(tk) -> bool:
    phonemes = getattr(tk, "phonemes", "") or ""
    return any(c.isalnum() for c in tk.text) or any(c.isalpha() for c in phonemes)


def timings_from_results(results, sample_rate: int = SAMPLE_RATE) -> list[dict]:
    words: list[dict] = []  # internal "ws" key = whitespace after the word
    pending = ""  # opening punctuation waiting for the next word
    offset = 0.0
    for r in results:
        chunk_end = offset + (len(r.audio) / sample_rate if r.audio is not None else 0.0)
        for tk in r.tokens or []:
            text, ws = tk.text, tk.whitespace or ""
            timed = tk.start_ts is not None and tk.end_ts is not None
            if _is_spoken(tk):
                if timed:
                    start = offset + tk.start_ts
                elif words:  # previous word may itself be untimed (end still None)
                    start = words[-1]["end"] if words[-1]["end"] is not None else words[-1]["start"]
                else:
                    start = offset
                if words and words[-1]["end"] is None:
                    words[-1]["end"] = start
                words.append({"word": pending + text, "start": start,
                              "end": offset + tk.end_ts if timed else None, "ws": ws})
                pending = ""
            elif pending or not words or (not ws and words[-1]["ws"]):
                pending += text + ws
            else:
                prev = words[-1]
                prev["word"] += prev["ws"] + text
                prev["ws"] = ws
                if timed and prev["end"] is not None:
                    prev["end"] = max(prev["end"], offset + tk.end_ts)
        if words:
            if words[-1]["end"] is None:
                words[-1]["end"] = chunk_end
            words[-1]["ws"] = words[-1]["ws"] or " "  # chunks split at spaces
        offset = chunk_end
    if pending and words:
        words[-1]["word"] += words[-1]["ws"] + pending
    return [{"word": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3)}
            for w in words]


def align(text: str, timings: list[dict]) -> list[dict]:
    """Add char_start/char_end to each timing: where its word sits in `text`.

    A cursor moves forward through the text; each word is searched for from
    the cursor ("the the" -> two different spans; spans never overlap). If the
    word isn't found, its letters-and-digits core is tried (in case Kokoro
    normalized a quote or dash). On a miss the span is None and the cursor
    stays put, so one unmatched word never derails the rest of the sentence.
    The search only looks ALIGN_LOOKAHEAD characters past the cursor, so a
    missed short word can't latch onto a far-away duplicate and skip text.

    Offsets are UTF-16 code units (JavaScript string indices), not Python
    code points: a character outside the BMP (emoji, math letters like 𝑥 in
    PDFs) counts as 2, as it does in the browser.
    """
    utf16 = [0]
    for ch in text:
        utf16.append(utf16[-1] + (2 if ord(ch) > 0xFFFF else 1))

    aligned = []
    cursor = 0
    for t in timings:
        span = _find(text, t["word"], cursor)
        if span is None:
            aligned.append({**t, "char_start": None, "char_end": None})
            continue
        start, end = span
        aligned.append({**t, "char_start": utf16[start], "char_end": utf16[end]})
        cursor = end
    return aligned


def _find(text: str, word: str, cursor: int) -> tuple[int, int] | None:
    for candidate in (word, _core(word)):
        if not candidate:
            continue
        limit = cursor + len(candidate) + ALIGN_LOOKAHEAD
        i = text.find(candidate, cursor, limit)
        if i >= 0:
            return i, i + len(candidate)
    return None


def _core(word: str) -> str:
    """The word without leading/trailing non-alphanumerics: '“quoted”' -> 'quoted'."""
    chars = [i for i, c in enumerate(word) if c.isalnum()]
    return word[chars[0]:chars[-1] + 1] if chars else ""
