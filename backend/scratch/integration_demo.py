"""Day 3 integration check: PDF -> sentences -> Day 2 cache -> WAVs to listen to.

    python scratch\\integration_demo.py [file.pdf|file.docx] [first] [last]
Copies each clip to scratch\\out\\day3\\ with a readable name.
"""
import shutil
import sys
import time
from pathlib import Path

from synth import get_pipeline, speak

from app.services.extractor import extract
from app.services.splitter import split

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
path = Path(sys.argv[1]) if len(sys.argv) > 1 else FIXTURES / "sample.pdf"
first, last = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 2)
OUT = Path(__file__).parent / "out" / "day3"
OUT.mkdir(parents=True, exist_ok=True)

get_pipeline("a")
for s in split(extract(path))[first:last + 1]:
    t = time.perf_counter()
    wav, timings, hit = speak(s.text, "af_heart", 1.0)
    name = OUT / f"{path.stem}_{s.idx:03d}.wav"
    shutil.copyfile(wav, name)
    print(f"[{s.idx}] (p.{s.page}) {'HIT ' if hit else 'MISS'} {(time.perf_counter() - t) * 1000:7.0f} ms  "
          f"{len(timings):3d} words  -> {name.name}\n      {s.text}")
