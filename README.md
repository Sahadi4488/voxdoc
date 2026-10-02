# VoxDoc

Upload a PDF or Word document; VoxDoc reads it aloud with Kokoro TTS, highlights each
word as it's spoken, and summarises it with gpt-oss on Groq. Runs on a CPU-only laptop.

- `backend/`: FastAPI, SQLite, Kokoro-82M (speech), all-MiniLM-L6-v2 (retrieval), Groq (summaries)
- `frontend/`: React 19, Vite, Tailwind v4

## Run it locally (Windows, PowerShell)

```powershell
# Backend: Python 3.11, project-local virtual environment
cd backend
uv python install 3.11          # if Python 3.11 isn't installed
uv venv --seed --python 3.11 .venv
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # then paste your Groq key into .env (optional)
.venv\Scripts\fastapi dev app/main.py    # http://127.0.0.1:8000/docs

# Frontend, in a second terminal
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

**Configuration** comes from environment variables or `backend/.env` (git-ignored), all
prefixed `VOXDOC_`; see `backend/.env.example` and `backend/app/config.py`. Without
`VOXDOC_GROQ_API_KEY` the app still runs: reading and audio work, and summaries answer
503 "AI features aren't configured on this server".

**Tests**, from `backend/`:

```powershell
.venv\Scripts\python -m pytest -q          # fast suite: fakes for Kokoro, MiniLM and Groq
.venv\Scripts\python -m pytest -q -m slow  # loads the real Kokoro and MiniLM models
.venv\Scripts\python -m pytest -q -m groq  # one live Groq call; skipped without a key
```

## Measurements

Laptop CPU (no GPU), on AC power. Scripts in `backend/scratch/` reproduce them.

### Summaries (Day 12): `scratch/summary_eval.py`

Groq free plan: 8,000 tokens per minute per model, 200,000 per day. A summary is one
request of at most ~5,000 estimated input tokens plus 1,200 output tokens (`openai/gpt-oss-20b`,
`reasoning_effort="low"`). Documents over the budget are summarised from selected passages:
the first two chunks, the last one, and chunks spread evenly in between.

| Document | Source | First summary | Cached | Prompt tokens (est. len/4 → real) | Estimate error | Completion tokens (reasoning) |
|---|---|---|---|---|---|---|
| sample.docx (17 sentences) | full | _pending_ | | | | |
| sample.pdf (3 pages) | full | _pending_ | | | | |
| attention.pdf (15 pages) | excerpts | _pending_ | | | | |

Excerpt selection, even spacing vs. MMR (`scratch/excerpt_selection_eval.py`, 15-page paper,
105 chunks of which 24 are reference-list entries): even spacing covers the document best
(mean similarity of each chunk to its closest excerpt 0.810, against 0.699–0.811 for MMR with
λ = 0.3–0.9). MMR only spends less of the budget on the reference list (10–12% against 19%)
by weighting relevance heavily, which costs coverage. Even spacing is shipped.

### Earlier days

| What | Result |
|---|---|
| Gap between sentences while playing (Day 8) | 35–45 ms with prefetch, 1.76 s without |
| First audio after opening a document (Day 8) | ~0.55 s |
| Words aligned to the text for highlighting (Day 10) | 100%: 595/595 (sample.pdf), 1,098/1,098 (60 sentences of the arXiv paper) |
| Highlight lag behind the audio (Day 10) | 11 ms on average, 14 ms max |
| Retrieval hit@1 / hit@4 (Day 11, `scratch/retrieval_eval.py`) | 30% / 90% (sample.pdf), 60% / 70% (arXiv paper) |
| Top score, on-topic vs off-topic questions (Day 11) | ≥ 0.277 vs ≤ 0.166 |
| Indexing the 15-page PDF / one retrieval (Day 11) | 2.0 s / 9 ms |
| RAM with Kokoro and MiniLM loaded (Day 11) | ~1.9 GB, peak 2.1 GB |
