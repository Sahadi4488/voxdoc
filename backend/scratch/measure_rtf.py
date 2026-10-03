"""Day 15: real-time factor (synthesis time / audio length) for each of the 7 presets.

    python scratch\\measure_rtf.py

Synthesises the first 8 sentences of sample.pdf with each preset at its default speed,
through the same TTSEngine the API uses (no cache), after a warm-up per voice. Three
rounds; the table shows the median RTF per preset. Lower is faster; 0.25 means one
second of speech takes 0.25 s to generate.
"""
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch  # noqa: E402

from app.services import extractor, splitter  # noqa: E402
from app.services.tts_engine import TTSEngine  # noqa: E402
from app.services.voices import PRESETS  # noqa: E402

SR = 24000
ROUNDS = 3
SENTENCES = 8
PDF = Path(__file__).resolve().parents[1] / "tests/fixtures/sample.pdf"

sentences = [s.text for s in splitter.split(extractor.extract(PDF))][:SENTENCES]
words = sum(len(s.split()) for s in sentences)
print(f"{len(sentences)} sentences, {words} words, torch {torch.__version__}, "
      f"{torch.get_num_threads()} threads, {platform.processor()}\n")

engine = TTSEngine()
t0 = time.perf_counter()
engine.warm_up()
print(f"Model loaded in {time.perf_counter() - t0:.1f} s\n")
for p in PRESETS.values():
    engine.synthesize("Warm up this voice.", p.voice, p.default_speed)

rtf: dict[str, list[float]] = {p.id: [] for p in PRESETS.values()}
audio_s: dict[str, float] = {}
for _ in range(ROUNDS):
    for p in PRESETS.values():
        gen = dur = 0.0
        for text in sentences:
            t = time.perf_counter()
            audio, _ = engine.synthesize(text, p.voice, p.default_speed)
            gen += time.perf_counter() - t
            dur += len(audio) / SR
        rtf[p.id].append(gen / dur)
        audio_s[p.id] = dur

print(f"{'preset':<16}{'voice':<12}{'speed':>6}{'audio s':>9}{'RTF median':>12}{'min-max':>14}")
for p in PRESETS.values():
    r = rtf[p.id]
    print(f"{p.name:<16}{p.voice:<12}{p.default_speed:>6}{audio_s[p.id]:>9.1f}"
          f"{statistics.median(r):>12.3f}{f'{min(r):.3f}-{max(r):.3f}':>14}")
