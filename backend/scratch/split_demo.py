"""Day 3: print sentences for each fixture (or any files you pass).

    python scratch\\split_demo.py                    # both fixtures
    python scratch\\split_demo.py my.pdf --all       # your own file, every sentence
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.extractor import extract  # noqa: E402
from app.services.splitter import MAX_CHARS, split  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
args = [a for a in sys.argv[1:] if a != "--all"]
files = [Path(a) for a in args] or [FIXTURES / "sample.pdf", FIXTURES / "sample.docx"]
limit = None if "--all" in sys.argv else 15

for f in files:
    t = time.perf_counter()
    sentences = split(extract(f))
    print(f"\n=== {f.name}: {len(sentences)} sentences ({time.perf_counter() - t:.2f}s), "
          f"longest {max(len(s.text) for s in sentences)} chars (max {MAX_CHARS})")
    for s in sentences[:limit]:
        print(f"[{s.idx}] (p.{s.page}) {s.text}")
