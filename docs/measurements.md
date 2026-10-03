# VoxDoc measurements

Every number here was measured on the machine below unless a row says otherwise. Cells
marked _not yet measured_ stay blank until the run they name has happened. Scripts live
in `backend/scratch/`; run them from `backend/` with the virtual environment.

**Laptop:** AMD Ryzen 7 5800H (8 cores, 16 threads), 16 GB RAM, Windows 11 Home, no GPU
used, on AC power. Python 3.11, torch 2.14.1 (CPU build, 8 threads), Edge for browser
measurements. Server and browser run on the same laptop, so they share the CPU.

Test documents: `backend/tests/fixtures/sample.pdf` (3 pages, written for the tests),
`sample.docx` (17 sentences), and a 15-page arXiv paper ("Attention Is All You Need",
431 sentences, 105 retrieval chunks; not in the repo, place it at
`backend/scratch/out/attention.pdf`).

## Speech

### Real-time factor per voice: `scratch/measure_rtf.py`

Synthesis time divided by audio length; lower is faster. The first 8 sentences of
sample.pdf (99 words) per voice, at each voice's default speed, through the same
`TTSEngine` the API uses, without the cache, after one warm-up per voice. Median of
3 rounds.

| Voice (preset) | Kokoro voice | Speed | Audio | RTF median | Range |
|---|---|---|---|---|---|
| Narrator | af_heart | 1.0 | 42.8 s | 0.289 | 0.288–0.289 |
| Storyteller | af_bella | 0.95 | 47.0 s | 0.289 | 0.286–0.290 |
| Calm | af_nicole | 0.85 | 74.4 s | 0.290 | 0.284–0.299 |
| Presenter (default) | am_michael | 1.0 | 47.2 s | 0.300 | 0.296–0.330 |
| Energetic | am_fenrir | 1.1 | 40.1 s | 0.321 | 0.291–0.322 |
| Emma | bf_emma | 1.0 | 41.6 s | 0.305 | 0.287–0.315 |
| Scholar | bm_george | 1.0 | 47.2 s | 0.293 | 0.293–0.315 |

Model load (Kokoro weights and the US pipeline) took 5.6 s in this run.

### Time to first audio: `scratch/browser/first_audio.mjs`

Production setup (uvicorn serving the built frontend, Kokoro loaded at startup). Each
trial: empty audio cache, fresh browser context (no HTTP cache), open sample.pdf, press
Play. Measured in the page from the click until the audio element's `playing` event.
Sentence 0 is a 7-word title (3.8 s of speech).

| | Median | Range | Trials |
|---|---|---|---|
| Play pressed as soon as it appears | 1.18 s | 1.16–1.38 s | 5 |
| Play pressed after 3 s on the page (sentence 0 was prefetched while idle) | 38 ms | 38–40 ms | 5 |
| Jump to an uncached sentence (click sentence 8, 9 words; what a citation click does) | 1.17 s | 1.12–1.23 s | 10 |

Synthesis alone for sentence 0 takes ~1.1 s on this laptop; the rest is the request, the
WAV download and the browser starting playback. A second run of the committed script gave
1.14 s, 37 ms and 1.16 s. An earlier, less controlled run gave 1.1–2.2 s for the first
row while the browser was still busy starting up.

### Gap between sentences: `scratch/browser/sentence_gaps.mjs`

Dev setup (Vite + uvicorn), sample.pdf, 8 sentences played in a row, 2 runs per mode,
empty cache each run. Gap = `playing` of the next clip minus `ended` of the previous one.
`?noprefetch` turns the player's prefetch off (dev build only).

| Transition (from → to) | With prefetch | Without |
|---|---|---|
| title (7 words) → "Abstract." | 37, 38 ms | 562, 522 ms |
| "Abstract." (1 word) → 19 words | **987, 904 ms** | 2,575, 2,572 ms |
| 19 words → 19 words | 38, 40 ms | 2,416, 2,347 ms |
| 19 words → "1. Introduction" | 38, 37 ms | 630, 669 ms |
| "1. Introduction" (2 words) → 23 words | **584, 528 ms** | 2,440, 2,552 ms |
| 23 words → 22 words | 39, 39 ms | 3,018, 3,082 ms |
| 22 words → 6 words | 43, 37 ms | 956, 951 ms |
| **Median (14 transitions)** | **39 ms** | **2.4 s** |

A second run of the committed script gave a 40 ms median with prefetch and 2.3 s without;
the two slow transitions took 996/1,076 ms and 618/683 ms.

Prefetching one sentence ahead hides synthesis only when the clip playing lasts longer
than the next sentence takes to synthesise. A 1–2-word heading plays for ~1.7 s, less
than a 20-word sentence needs, hence the two slow transitions.

### Highlighting (Day 10)

| What | Result | How |
|---|---|---|
| Words aligned to the text | 100%: 595/595 (sample.pdf), 1,098/1,098 (60 sentences of the arXiv paper) | `scratch/align_rate.py` |
| Highlight lag behind the audio | 11 ms mean, 14 ms max; 0 of 3,282 frames showed the wrong word | Playwright, a paragraph at 1.0×: the marked word compared with the word timings at `audio.currentTime` on every frame |

## Retrieval (Day 11): `scratch/retrieval_eval.py`

10 questions per document with hand-labelled answer sentences; a hit means a retrieved
chunk contains a labelled sentence. all-MiniLM-L6-v2, NumPy dot product over the
document's chunk vectors.

| | sample.pdf | arXiv paper |
|---|---|---|
| hit@1 | 30% | 60% |
| hit@4 | 90% | 70% |
| Indexing (embedding every chunk) | | 2.0 s |
| One retrieval (embed the question + top-k), median | | 9 ms |

Top similarity score: on-topic questions ≥ 0.277, off-topic ≤ 0.166, so Q&A refuses below
0.22 without calling the LLM. RAM of the server with Kokoro and MiniLM loaded: ~1.9 GB,
peak 2.1 GB (`scratch/measure_indexing.py`).

## Summaries (Day 12): `scratch/summary_eval.py`

Groq free plan: 8,000 tokens per minute per model, 200,000 per day. A summary is one
request of at most ~5,000 estimated input tokens plus 1,200 output tokens
(`openai/gpt-oss-20b`, `reasoning_effort="low"`). Documents over the budget are summarised
from selected passages: the first two chunks, the last one, and chunks spread evenly in
between.

| Document | Source | First summary | Cached | Prompt tokens (est. len/4 → real) | Estimate error | Completion tokens (reasoning) |
|---|---|---|---|---|---|---|
| sample.docx (17 sentences) | full | _not yet measured_ | | | | |
| sample.pdf (3 pages) | full | _not yet measured_ | | | | |
| attention.pdf (15 pages) | excerpts | _not yet measured_ | | | | |

Excerpt selection, even spacing vs. MMR (`scratch/excerpt_selection_eval.py`, the 15-page
paper, 105 chunks of which 24 are reference-list entries): even spacing covers the
document best (mean similarity of each chunk to its closest excerpt 0.810, against
0.699–0.811 for MMR with λ = 0.3–0.9). MMR only spends less of the budget on the reference
list (10–12% against 19%) by weighting relevance heavily, which costs coverage. Even
spacing is shipped.

## Questions with citations (Day 13): `scratch/qa_eval.py`

The Day 11 question set asked through the real pipeline: MiniLM retrieval (top 5 chunks),
the 0.22 threshold, then `openai/gpt-oss-120b` with `reasoning_effort="low"`. A citation
hit means the answer cites a labelled answer sentence.

| | sample.pdf (3 pages) | attention.pdf (15 pages) |
|---|---|---|
| Citation hit rate | _not yet measured_ | _not yet measured_ |
| Answer sentence among those sent (the ceiling for the above) | 9 / 10 | 7 / 10 |
| Off-topic questions refused, and Groq calls spent on them | 3 / 3, 0 calls | 3 / 3, 0 calls |
| On-topic questions wrongly refused by the threshold | 0 / 10 | 0 / 10 |
| Average answer latency | _not yet measured_ | _not yet measured_ |

## Production build (Day 14)

| | Container (`.github/workflows/docker.yml` on a GitHub runner) | Laptop, same setup without Docker (`scratch/measure_production.py`) |
|---|---|---|
| Image size | _not yet measured_ | — |
| Cold start (process start until `/api/health` answers, Kokoro loaded) | _not yet measured_ | 11.2 s |
| Time to first audio (API request until the WAV is downloaded) | _not yet measured_ | 1.5 s |
| Peak RAM (Kokoro; MiniLM adds ~0.3 GB once a question is asked) | _not yet measured_ | 1.63 GB |
