"""Convert Kokoro pipeline results into word timings.

Format: [{"word": str, "start": float, "end": float}, ...] in seconds,
relative to the start of the concatenated audio. Every entry contains at
least one letter or digit; the entries joined with spaces rebuild the text.

Token policy (decided Day 2, the frontend depends on it):
- Punctuation/symbol tokens never become entries of their own. Kokoro times
  most punctuation (",", "?", ")" ...) but returns None for tokens without
  phonemes ("$", "#", "--").
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


def timings_from_results(results, sample_rate: int = SAMPLE_RATE) -> list[dict]:
    words: list[dict] = []  # internal "ws" key = whitespace after the word
    pending = ""  # opening punctuation waiting for the next word
    offset = 0.0
    for r in results:
        chunk_end = offset + (len(r.audio) / sample_rate if r.audio is not None else 0.0)
        for tk in r.tokens or []:
            text, ws = tk.text, tk.whitespace or ""
            timed = tk.start_ts is not None and tk.end_ts is not None
            if any(c.isalnum() for c in text):
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
