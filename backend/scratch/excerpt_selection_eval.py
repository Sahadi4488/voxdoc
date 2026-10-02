"""Day 12 stretch: choose summary excerpts by even spacing (shipped) or by
Maximal Marginal Relevance (MMR), compared without spending Groq quota.

    python scratch\\excerpt_selection_eval.py

MMR picks, one at a time, the chunk that maximises
    lambda * sim(chunk, document centroid) - (1 - lambda) * max sim(chunk, already picked)
using the Day 11 MiniLM vectors, starting from the same first-two + last chunks.

Metrics on the 15-page arXiv paper (105 chunks):
- coverage: mean over all chunks of the cosine similarity to the closest picked
  chunk (how well the excerpts stand in for the whole document);
- body coverage: the same over the paper's body only (no reference list);
- budget spent on reference-list chunks (useless for a summary).
"""
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import db  # noqa: E402
from app.config import settings  # noqa: E402
from app.services.embeddings import Embedder, from_blob  # noqa: E402
from app.services.extractor import extract  # noqa: E402
from app.services.indexer import ensure_indexed  # noqa: E402
from app.services.splitter import split  # noqa: E402
from app.services.summarizer import (INPUT_BUDGET, _render, estimate_tokens, render_prompt,  # noqa: E402
                                     select_excerpts)

PDF = BACKEND / "scratch/out/attention.pdf"


def mmr(costs, vectors, budget, lam):
    n = len(costs)
    sims = vectors @ vectors.T
    centroid = vectors.mean(0)
    relevance = vectors @ (centroid / np.linalg.norm(centroid))
    picked, used = [], 0
    for i in dict.fromkeys(p for p in (0, 1, n - 1) if 0 <= p < n):
        if used + costs[i] <= budget:
            picked.append(i)
            used += costs[i]
    while True:
        fits = [i for i in range(n) if i not in picked and used + costs[i] <= budget]
        if not fits:
            return sorted(picked)
        best = max(fits, key=lambda i: lam * relevance[i] - (1 - lam) * sims[i, picked].max())
        picked.append(best)
        used += costs[best]


if __name__ == "__main__":
    if not PDF.exists():
        sys.exit(f"{PDF} missing (download the arXiv paper as on Day 3)")
    settings.db_path = Path(tempfile.mkdtemp()) / "eval.db"
    db.init_db()
    conn = db.connect()
    embedder = Embedder()
    sentences = split(extract(PDF))
    pk = db.get_doc_pk(conn, db.insert_document(conn, "attention", PDF.name, f"{time.time_ns()}", sentences))
    ensure_indexed(conn, pk, embedder)
    rows = db.get_chunks(conn, pk, embedder.model_name)
    vectors = np.stack([from_blob(r["embedding"]) for r in rows])
    ranges = [(r["start_idx"], r["end_idx"]) for r in rows]
    costs = [estimate_tokens(_render(sentences[a:b + 1])) + 2 for a, b in ranges]
    budget = INPUT_BUDGET - estimate_tokens(render_prompt("attention", "", excerpts=True))
    # Reference-list chunks: sentences starting "[12] Author..."
    is_ref = np.array([any(s.text.startswith("[") and "]" in s.text[:5] for s in sentences[a:b + 1])
                       for a, b in ranges])
    print(f"{len(ranges)} chunks, {is_ref.sum()} of them reference-list entries; "
          f"excerpt budget {budget} estimated tokens\n")

    def report(name, picked):
        closest = (vectors @ vectors[picked].T).max(1)
        on_refs = sum(costs[i] for i in picked if is_ref[i]) / sum(costs[i] for i in picked)
        print(f"{name:13s} {len(picked):3d} chunks   coverage {closest.mean():.3f}   "
              f"body coverage {closest[~is_ref].mean():.3f}   budget on references {on_refs:5.1%}")

    report("even spacing", select_excerpts(costs, budget))
    for lam in (0.3, 0.5, 0.7, 0.9):
        report(f"MMR λ={lam}", mmr(costs, vectors, budget, lam))
    conn.close()
