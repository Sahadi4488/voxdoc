"""What do the stored word timings look like for tricky sentences? (input for align())"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.tts_engine import TTSEngine  # noqa: E402

engine = TTSEngine()
for text in [
    "I don't know.",
    "The U.S. grew 3.5% in 2024.",
    "the the",
    "Dr. Smith’s café is naïve — “quoted” and 'single' (really?) costs $5 & 20%... OK.",
    "Read Fig. 3, e.g. the state-of-the-art model at 3 p.m.",
]:
    audio, timings = engine.synthesize(text, "af_heart", 1.0)
    print(f"\n{text!r}  ({len(audio) / 24000:.2f}s)")
    print("   ", [w["word"] for w in timings])
