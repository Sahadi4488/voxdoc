"""Split a document's sentences into overlapping chunks for retrieval.

Chunks are runs of consecutive sentences only, so every chunk maps to a
citable sentence range (Day 13). Sizes are measured in the embedding model's
tokens, not words: all-MiniLM-L6-v2 reads only the first 256 tokens and
silently ignores the rest, and technical text runs ~2.8 tokens per word
("[38, 24, 15]", "41.8", "t−1") against ~1.2 for prose, so a word limit
can't guarantee the fit.

Rules:
- Grow a chunk to about TARGET_TOKENS, never past MAX_TOKENS.
- Close it early at a paragraph end once it has at least half the target.
- Consecutive chunks overlap by one sentence, so an answer that falls across
  a boundary is still found whole in one of them.
- A sentence that alone exceeds MAX_TOKENS becomes its own chunk (the model
  then embeds only its start: a known, rare loss; the splitter caps sentences
  at 350 characters).
- Every new chunk starts at least one sentence after the previous one
  started, so the overlap can never stall the window (no infinite loop).
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.services.splitter import Sentence

TARGET_TOKENS = 160  # ~120 words of prose
MAX_TOKENS = 256  # all-MiniLM-L6-v2 max_seq_length, counting [CLS] and [SEP]


@dataclass(frozen=True)
class Chunk:
    idx: int
    text: str
    start_idx: int  # first sentence idx (inclusive)
    end_idx: int  # last sentence idx (inclusive)


def estimate_tokens(text: str) -> int:
    """Rough fallback when no tokenizer is at hand (tests): words * 1.4 + [CLS]/[SEP]."""
    return int(len(text.split()) * 1.4) + 2


def chunk(
    sentences: Sequence[Sentence],
    count_tokens: Callable[[str], int] = estimate_tokens,
    target: int | None = None,
    limit: int | None = None,
) -> list[Chunk]:
    target = TARGET_TOKENS if target is None else target  # read at call time, not import time
    limit = MAX_TOKENS if limit is None else limit
    n = len(sentences)
    if n == 0:
        return []
    # Each sentence's size without the 2 special tokens, which a chunk pays once
    sizes = [max(count_tokens(s.text) - 2, 1) for s in sentences]
    budget, goal = limit - 2, target - 2

    chunks: list[Chunk] = []
    start = 0
    while start < n:
        end = start
        size = sizes[start]
        while end + 1 < n:
            if size >= goal or size + sizes[end + 1] > budget:
                break
            if sentences[end].para != sentences[end + 1].para and size >= goal / 2:
                break  # a paragraph ends here and the chunk is big enough
            end += 1
            size += sizes[end]
        chunks.append(Chunk(
            idx=len(chunks),
            text=" ".join(s.text for s in sentences[start:end + 1]),
            start_idx=sentences[start].idx,
            end_idx=sentences[end].idx,
        ))
        if end == n - 1:
            break
        # Overlap by one sentence, unless the overlap sentence and the next one
        # can't share a chunk anyway (that chunk would just repeat the overlap).
        next_start = end if sizes[end] + sizes[end + 1] <= budget else end + 1
        start = max(next_start, start + 1)
    return chunks
