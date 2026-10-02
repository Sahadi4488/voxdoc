"""Day 12 measurements with the real Groq key, on a real server process:
summary latency (first and cached), tokens used, how far the len/4 estimate is
from Groq's prompt_tokens, and "two simultaneous clicks = one Groq call".

    python scratch\\summary_eval.py

Own data folder and port 8001: your data/ is untouched. Reads the numbers from
the server's log lines (llm.py logs every call's usage). Spends ~12,000 tokens
and waits a minute in the middle, so the 15-page paper's ~6,000-token request
and the rest don't share one minute of the 8,000 tokens/minute limit.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import settings  # noqa: E402

API = "http://127.0.0.1:8001"
DOCS = ["scratch/out/attention.pdf", "tests/fixtures/sample.pdf", "tests/fixtures/sample.docx"]
ESTIMATE = re.compile(r"summarizing document \d+: (\w+) text, ~(\d+) prompt tokens estimated")
USAGE = re.compile(r"groq (\S+): (\d+) prompt \+ (\d+) completion tokens(?: \((\d+) reasoning\))?, ([\d.]+) s")


class Log:
    """The server's stderr, read in pieces: new lines since the last call."""

    def __init__(self, path):
        self.path, self.pos = path, 0

    def new(self):
        text = self.path.read_text(encoding="utf-8", errors="replace")
        out, self.pos = text[self.pos:], len(text)
        return out


def upload(c, path):
    with open(BACKEND / path, "rb") as f:
        r = c.post("/documents", files={"file": (Path(path).name, f, "application/octet-stream")})
    r.raise_for_status()
    return r.json()["id"]


def summarize(c, doc_id):
    t = time.perf_counter()
    r = c.post(f"/documents/{doc_id}/summary")
    return r, time.perf_counter() - t


def main():
    if settings.groq_api_key is None:
        sys.exit("No VOXDOC_GROQ_API_KEY in backend/.env")
    data = Path(tempfile.mkdtemp())
    log = Log(data / "server.log")
    env = {**os.environ, "VOXDOC_DATA_DIR": str(data), "PYTHONWARNINGS": "ignore",
           "HF_HUB_DISABLE_SYMLINKS_WARNING": "1", "PYTHONUTF8": "1"}
    with open(log.path, "w", encoding="utf-8") as out:
        proc = subprocess.Popen([str(BACKEND / ".venv/Scripts/fastapi.exe"), "run", "app/main.py", "--port", "8001"],
                                cwd=BACKEND, env=env, stdout=out, stderr=out)
    rows = []
    try:
        with httpx.Client(base_url=API, timeout=180) as c:
            for _ in range(240):
                try:
                    if c.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.5)
            log.new()
            for i, path in enumerate(DOCS):
                if not (BACKEND / path).exists():
                    print(f"(skipping {path}: not found)")
                    continue
                if i == 1:
                    print("waiting 65 s for the tokens-per-minute window to clear...")
                    time.sleep(65)
                doc_id = upload(c, path)
                first, first_s = summarize(c, doc_id)
                cached, cached_s = summarize(c, doc_id)
                lines = log.new()
                assert first.status_code == 200, first.text
                est = ESTIMATE.search(lines)
                calls = USAGE.findall(lines)
                body = first.json()
                rows.append({"doc": Path(path).name, "source": body["source"], "first_s": first_s,
                             "cached_s": cached_s, "cached": cached.json()["cached"], "estimate": int(est[2]),
                             "calls": [(int(p), int(c_), int(r or 0), float(s)) for _, p, c_, r, s in calls]})
                print(json.dumps(body, indent=2, ensure_ascii=False))

            # Two clicks at the same moment on a fresh document: one Groq call
            doc_id = upload(c, "tests/fixtures/sample.docx")
            results = []
            threads = [threading.Thread(target=lambda: results.append(summarize(c, doc_id)[0])) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            concurrent_calls = len(USAGE.findall(log.new()))
            concurrent_cached = sorted(r.json()["cached"] for r in results)
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)

    print("\n| Document | Source | First summary | Cached | Prompt tokens (est. len/4 → real) | Estimate error "
          "| Completion tokens (reasoning) | Groq time |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        prompt, completion, reasoning, groq_s = r["calls"][-1]
        err = (r["estimate"] - prompt) / prompt
        retried = f" ({len(r['calls'])} calls)" if len(r["calls"]) > 1 else ""
        print(f"| {r['doc']} | {r['source']} | {r['first_s']:.2f} s{retried} | {r['cached_s'] * 1000:.0f} ms "
              f"| {r['estimate']} → {prompt} | {err:+.1%} | {completion} ({reasoning}) | {groq_s:.2f} s |")
        assert r["cached"] and prompt + completion < 8000
    print(f"\nTwo simultaneous requests: {concurrent_calls} Groq call(s), cached flags {concurrent_cached}")


if __name__ == "__main__":
    main()
