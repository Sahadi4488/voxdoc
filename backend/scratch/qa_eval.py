"""Day 13 Part F: citation evaluation with the real MiniLM and the real Groq.

For each Day 11 question (scratch/retrieval_eval.py), ask through the real
answer_question() and record:
- citation hit: the answer cites a gold sentence (one containing the label phrase);
- gold in context: a gold sentence was among those sent, so a miss there is
  retrieval's fault, not the citations';
- found / grounded, latency (retrieval + Groq) and tokens;
then whether the 3 off-topic questions per document are refused ("not
found"), and whether refusing them cost a Groq call.

    python scratch\\qa_eval.py            # reasoning_effort "low", as shipped
    python scratch\\qa_eval.py medium     # the comparison, if "low" cites poorly

Spends ~40,000 tokens (of 200,000 a day) and paces itself to the free plan's
8,000 tokens per minute: about 8 minutes.
"""
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scratch"))

import groq  # noqa: E402

from app import db  # noqa: E402
from app.config import settings  # noqa: E402
from app.services import qa  # noqa: E402
from app.services.embeddings import Embedder  # noqa: E402
from app.services.extractor import extract  # noqa: E402
from app.services.llm import LLMBusy, LLMClient  # noqa: E402
from app.services.splitter import split  # noqa: E402
from retrieval_eval import OFF_TOPIC, SETS  # noqa: E402

PACE_S = 16  # ~2K tokens per question (prompt + reserved output) against 8K per minute


class Counting:
    """Wraps the real Groq client: keeps every prompt sent and every response."""

    def __init__(self, inner):
        self.inner, self.prompts, self.responses = inner, [], []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        resp = self.inner.chat.completions.create(**kwargs)
        self.responses.append(resp)
        return resp


def ask(conn, pk, question, llm, embedder):
    for attempt in (1, 2):
        try:
            started = time.perf_counter()
            return qa.answer_question(conn, pk, question, llm, embedder), time.perf_counter() - started
        except LLMBusy as e:
            if attempt == 2:
                raise
            print(f"    (rate limited, waiting {e.retry_after} s)")
            time.sleep(e.retry_after + 1)


def main():
    if settings.groq_api_key is None:
        sys.exit("No VOXDOC_GROQ_API_KEY in backend/.env")
    if len(sys.argv) > 1:
        qa.REASONING_EFFORT = sys.argv[1]
    print(f"model {settings.groq_qa_model}, reasoning_effort={qa.REASONING_EFFORT}, "
          f"threshold {settings.qa_min_score}\n")
    settings.db_path = Path(tempfile.mkdtemp()) / "eval.db"
    db.init_db()
    conn = db.connect()
    embedder = Embedder()
    embedder.warm_up()
    groq_client = Counting(groq.Groq(api_key=settings.groq_api_key.get_secret_value(), timeout=30, max_retries=1))
    llm = LLMClient(settings.groq_api_key, client=groq_client)

    latencies, report = [], []
    for path, questions in SETS.items():
        if not (BACKEND / path).exists():
            print(f"(skipping {path}: not found)")
            continue
        sentences = split(extract(BACKEND / path))
        pk = db.get_doc_pk(conn, db.insert_document(conn, Path(path).stem, path, f"{time.time_ns()}", sentences))
        print(f"=== {Path(path).name}")
        hits = in_context = grounded = 0
        for question, phrase in questions:
            gold = {s.idx for s in sentences if phrase.lower() in s.text.lower()}
            calls_before = len(groq_client.responses)
            answer, seconds = ask(conn, pk, question, llm, embedder)
            shown = set()
            if len(groq_client.responses) > calls_before:
                latencies.append(seconds)
                # The sentence numbers actually sent: the "[S12] ..." lines of the prompt
                shown = {int(n) for n in re.findall(r"^\[S(\d+)\]", groq_client.prompts[-1], re.MULTILINE)}
                last = groq_client.responses[-1]
                usage = f"{last.usage.prompt_tokens}+{last.usage.completion_tokens} tokens"
            else:
                usage = "no Groq call"
            hit = bool(gold & set(answer.citations))
            hits += hit
            in_context += bool(gold & shown)
            grounded += answer.grounded
            text = "".join(p.get("text", f"[{p.get('cite')}]") for p in answer.parts)
            print(f"  {'HIT ' if hit else 'miss'} gold {sorted(gold)} cited {answer.citations} "
                  f"{'(gold in context)' if gold & shown else '(gold NOT in context)'} {seconds:.1f} s, {usage}")
            print(f"       Q: {question}\n       A: {text}")
            time.sleep(PACE_S)
        refused = calls = 0
        for question in OFF_TOPIC:
            calls_before = len(groq_client.responses)
            answer, _ = ask(conn, pk, question, llm, embedder)
            refused += not answer.found
            calls += len(groq_client.responses) - calls_before
            print(f"  off-topic {'refused' if not answer.found else 'ANSWERED'}: {question}")
        n = len(questions)
        report.append(f"{Path(path).name}: citation hit {hits}/{n} (gold sentence sent {in_context}/{n}), "
                      f"grounded {grounded}/{n}, off-topic refused {refused}/{len(OFF_TOPIC)} "
                      f"with {calls} Groq call(s)")
        print()
    conn.close()
    print("\n".join(report))
    usage = [(r.usage.prompt_tokens, r.usage.completion_tokens) for r in groq_client.responses]
    print(f"answer latency: mean {statistics.mean(latencies):.2f} s, median {statistics.median(latencies):.2f} s, "
          f"max {max(latencies):.2f} s over {len(latencies)} answers")
    print(f"tokens per answer: mean {statistics.mean(p for p, _ in usage):.0f} prompt + "
          f"{statistics.mean(c for _, c in usage):.0f} completion")


if __name__ == "__main__":
    main()
