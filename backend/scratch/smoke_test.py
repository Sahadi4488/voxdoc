"""Day 1 A4 smoke test + RTF table + timestamp inspection.

Run from backend\\:  python scratch\\smoke_test.py
"""
import time
from pathlib import Path

import soundfile as sf
import torch
from kokoro import KPipeline

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.timings import timings_from_results  # noqa: E402

SR = 24000
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

SENTENCE = "VoxDoc reads your documents aloud, one sentence at a time."
VOICES = ["af_heart", "af_bella", "af_nicole", "am_michael", "am_fenrir", "bf_emma", "bm_george"]

t0 = time.perf_counter()
pipe_a = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
pipe_b = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M", model=pipe_a.model)  # share weights
pipes = {"a": pipe_a, "b": pipe_b}
print(f"Pipelines ready in {time.perf_counter() - t0:.1f}s\n")


def synth(text, voice, speed=1.0):
    results = list(pipes[voice[0]](text, voice=voice, speed=speed))
    audio = torch.cat([r.audio for r in results]).cpu().numpy()
    return audio, results


# Warm-up + preload every voice file, so timings measure synthesis only
synth("Warm up.", "af_heart")
for v in VOICES:
    pipes[v[0]].load_voice(v)

print(f"{'voice':<12}{'audio s':>9}{'gen s':>8}{'RTF':>7}")
for v in VOICES:
    t = time.perf_counter()
    audio, _ = synth(SENTENCE, v)
    gen = time.perf_counter() - t
    dur = len(audio) / SR
    sf.write(OUT / f"smoke_{v}.wav", audio, SR)
    print(f"{v:<12}{dur:>9.2f}{gen:>8.2f}{gen / dur:>7.3f}")

print("\nTokens for one sentence (af_heart):")
_, results = synth("Hello, world! This is VoxDoc; it reads PDFs.", "af_heart")
for r in results:
    for tk in r.tokens:
        print(f"  {tk.text!r:<12} start={tk.start_ts!s:<8} end={tk.end_ts!s:<8} phonemes={tk.phonemes!r}")

print("\nProcessed word timings (app/services/timings.py):")
for w in timings_from_results(results):
    print("  ", w)

print("\nLong input - do timestamps restart per result?")
long_text = " ".join(["This sentence is padded with plenty of extra words so the pipeline has to split it."] * 8)
_, results = synth(long_text, "af_heart")
for i, r in enumerate(results):
    timed = [tk for tk in r.tokens if tk.start_ts is not None]
    print(f"  result {i}: audio {len(r.audio) / SR:.2f}s, first word start={timed[0].start_ts}, last word end={timed[-1].end_ts}")
words = timings_from_results(results)
print(f"  after offsetting: {len(words)} words, first starts {words[0]['start']}s, last ends {words[-1]['end']}s "
      f"(total audio {sum(len(r.audio) for r in results) / SR:.2f}s)")
