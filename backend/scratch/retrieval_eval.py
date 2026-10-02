"""Day 11 retrieval evaluation: hit@1 / hit@4 on hand-labelled questions, plus
the top score of off-topic questions (to set Day 13's "not in the document"
threshold from data). Runs the real chunker, MiniLM and retriever against a
throwaway database.

    python scratch\\retrieval_eval.py

A label is a phrase from the answering sentence(s); a hit means a returned
chunk's sentence range contains an answering sentence.
"""
import statistics
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import db  # noqa: E402
from app.config import settings  # noqa: E402
from app.services.embeddings import Embedder  # noqa: E402
from app.services.extractor import extract  # noqa: E402
from app.services.indexer import ensure_indexed  # noqa: E402
from app.services.retriever import retrieve  # noqa: E402
from app.services.splitter import split  # noqa: E402

SETS = {
    "tests/fixtures/sample.pdf": [
        ("How many parameters does the speech model have?", "eighty-two million"),
        ("How many documents were used to test the reader?", "forty documents"),
        ("What did listeners complain about most?", "most common complaint"),
        ("Which voices did people like for novels and stories?", "British voices for fiction"),
        ("How fast is speech generation compared with real time?", "three times faster"),
        ("Does VoxDoc need a GPU?", "dedicated graphics card"),
        ("What are the steps of the processing pipeline?", "four stages"),
        ("How long until the first sentence plays when nothing is cached?", "about one second"),
        ("What features are planned next?", "Future work"),
        ("Why is a reader on your own computer better than cloud services?", "send private files"),
    ],
    "scratch/out/attention.pdf": [  # 15-page arXiv paper, local only (not redistributable)
        ("What BLEU score does the model reach on English-to-French?", "41.8"),
        ("How long did training the big model take?", "3.5 days"),
        ("Which optimizer was used?", "Adam optimizer"),
        ("How is the learning rate changed during training?", "warmup_steps"),
        ("How many layers are in the encoder stack?", "identical layers"),
        ("How are word positions represented?", "sine and cosine"),
        ("What does multi-head attention let the model do?", "jointly attend"),
        ("How big was the English-German training set?", "4.5 million sentence pairs"),
        ("What regularization is used?", "label smoothing"),
        ("Does the model generalize to parsing?", "constituency parsing"),
    ],
}
OFF_TOPIC = ["What is the capital of France?", "How do I bake sourdough bread?", "Who won the 2018 World Cup?"]


def main():
    if len(sys.argv) > 1:  # chunk-size sweep: python scratch\retrieval_eval.py 80
        from app.services import chunker
        chunker.TARGET_TOKENS = int(sys.argv[1])
        print(f"TARGET_TOKENS = {chunker.TARGET_TOKENS}")

    tmp = Path(tempfile.mkdtemp())
    settings.db_path = tmp / "eval.db"
    db.init_db()
    embedder = Embedder()
    embedder.warm_up()
    conn = db.connect()

    summary = {"on": [], "off": []}
    for path, questions in SETS.items():
        if not (BACKEND / path).exists():
            print(f"\n(skipping {path}: not found)")
            continue
        sentences = split(extract(BACKEND / path))
        pk = db.get_doc_pk(conn, db.insert_document(conn, path, path, f"{time.time_ns()}", sentences))
        t = time.perf_counter()
        n_chunks = ensure_indexed(conn, pk, embedder)
        index_s = time.perf_counter() - t
        print(f"\n=== {Path(path).name}: {len(sentences)} sentences -> {n_chunks} chunks, indexed in {index_s:.1f} s")

        hit1 = hit4 = 0
        times, top_scores = [], []
        for q, phrase in questions:
            answers = {s.idx for s in sentences if phrase.lower() in s.text.lower()}
            if not answers:
                print(f"  ?? label {phrase!r} matches no sentence; skipped")
                continue
            t = time.perf_counter()
            hits = retrieve(conn, pk, q, embedder, k=4)
            times.append(time.perf_counter() - t)
            inside = [any(h.start_idx <= a <= h.end_idx for a in answers) for h in hits]
            hit1 += inside[0]
            hit4 += any(inside)
            top_scores.append(hits[0].score)
            rank = inside.index(True) + 1 if any(inside) else "-"
            print(f"  {'OK ' if inside[0] else ('ok4' if any(inside) else 'MISS')} rank {rank}  top {hits[0].score:.3f}  {q}")
        n = len(top_scores)
        print(f"  hit@1 {hit1}/{n} = {hit1 / n:.0%}   hit@4 {hit4}/{n} = {hit4 / n:.0%}   "
              f"retrieval {1000 * statistics.median(times):.0f} ms/question (median, model loaded)")
        off = [retrieve(conn, pk, q, embedder, k=1)[0].score for q in OFF_TOPIC]
        print(f"  on-topic top score: min {min(top_scores):.3f}, median {statistics.median(top_scores):.3f}")
        print(f"  off-topic top score: {', '.join(f'{s:.3f}' for s in off)}  ({', '.join(OFF_TOPIC)})")
        summary["on"] += top_scores
        summary["off"] += off

    print(f"\nOverall: lowest on-topic top score {min(summary['on']):.3f}, highest off-topic {max(summary['off']):.3f}")
    conn.close()


if __name__ == "__main__":  # scratch/qa_eval.py imports SETS
    main()
