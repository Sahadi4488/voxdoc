"""Alignment rate on real documents: what share of words get a character span?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.extractor import extract  # noqa: E402
from app.services.splitter import split  # noqa: E402
from app.services.tts_engine import TTSEngine  # noqa: E402

engine = TTSEngine()
for path, limit in [("tests/fixtures/sample.pdf", None), ("scratch/out/attention.pdf", 60)]:
    sents = split(extract(path))[:limit]
    total = aligned = 0
    below_half = []
    for s in sents:
        _, timings = engine.synthesize(s.text, "af_heart", 1.0)
        ok = [t for t in timings if t["char_start"] is not None]
        total += len(timings)
        aligned += len(ok)
        for t in timings:  # spans must be valid, ordered, non-overlapping
            pass
        ends = [t["char_end"] for t in ok]
        starts = [t["char_start"] for t in ok]
        assert all(0 <= a < b <= len(s.text) for a, b in zip(starts, ends)), s.text
        assert all(e <= st for e, st in zip(ends, starts[1:])), s.text
        if timings and len(ok) < len(timings) / 2:
            below_half.append(s.text)
        missed = [t["word"] for t in timings if t["char_start"] is None]
        if missed:
            print(f"  [{s.idx}] missed {missed} in: {s.text[:90]}")
    print(f"{Path(path).name}: {aligned}/{total} words aligned ({100 * aligned / total:.1f}%), "
          f"{len(below_half)} of {len(sents)} sentences would fall back to sentence highlighting")
