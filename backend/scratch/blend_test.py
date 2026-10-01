"""Day 2 Part C: voice-blend test.  Run from backend\\:
    python scratch\\blend_test.py
Writes WAVs to scratch\\out\\blend\\ - LISTEN to them to judge artifacts.
"""
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from synth import get_pipeline, synthesize

SR = 24000
OUT = Path(__file__).parent / "out" / "blend"
OUT.mkdir(parents=True, exist_ok=True)
SENTENCE = "The quick brown fox jumps over the lazy dog, then reads a chapter of history aloud."

# Sanity check: Kokoro's comma string is an equal average of the voice tensors
pa = get_pipeline("a")
avg = pa.load_voice("af_heart,af_bella")
manual = 0.5 * pa.load_voice("af_heart") + 0.5 * pa.load_voice("af_bella")
print(f"'af_heart,af_bella' == 0.5*a + 0.5*b : {torch.allclose(avg, manual, atol=1e-6)}  shape={tuple(avg.shape)}\n")


def spectrum(audio):
    """Average log-magnitude spectrum: a crude timbre fingerprint."""
    frames = np.lib.stride_tricks.sliding_window_view(audio, 1024)[::512] * np.hanning(1024)
    return np.log(np.abs(np.fft.rfft(frames)).mean(axis=0) + 1e-8)


def render(name, voice, lang_code=None):
    audio, timings = synthesize(SENTENCE, voice, lang_code=lang_code)
    sf.write(OUT / f"{name}.wav", audio, SR)
    return audio, timings


parents = {v: render(v, v)[0] for v in ["af_heart", "af_bella", "am_michael", "bf_emma"]}
fp = {v: spectrum(a) for v, a in parents.items()}

blends = [
    ("heart50_bella50", {"af_heart": 0.5, "af_bella": 0.5}, "a", ["af_heart", "af_bella"]),
    ("heart70_michael30", {"af_heart": 0.7, "am_michael": 0.3}, "a", ["af_heart", "am_michael"]),
    ("heart50_emma50_US", {"af_heart": 0.5, "bf_emma": 0.5}, "a", ["af_heart", "bf_emma"]),
    ("heart50_emma50_UK", {"af_heart": 0.5, "bf_emma": 0.5}, "b", ["af_heart", "bf_emma"]),
]
print(f"{'blend':<20}{'secs':>6}{'words':>7}{'peak':>7}  timbre distance to parents (0 = identical)")
for name, voice, lang, pars in blends:
    audio, timings = render(name, voice, lang)
    dists = ", ".join(f"{p}={np.abs(spectrum(audio) - fp[p]).mean():.3f}" for p in pars)
    ok = np.isfinite(audio).all() and timings
    print(f"{name:<20}{len(audio) / SR:>6.2f}{len(timings):>7}{np.abs(audio).max():>7.2f}  {dists}"
          f"{'' if ok else '  <-- PROBLEM'}")
print(f"\nParent-to-parent reference: heart vs bella = {np.abs(fp['af_heart'] - fp['af_bella']).mean():.3f}, "
      f"heart vs michael = {np.abs(fp['af_heart'] - fp['am_michael']).mean():.3f}")
print(f"WAVs in {OUT}")
