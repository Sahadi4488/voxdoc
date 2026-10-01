"""Which Kokoro tokens come back with start_ts/end_ts = None?"""
from synth import get_pipeline

p = get_pipeline("a")
text = 'She said, "Wait (really?) - it costs $5 & 20%... OK" -- fine: #1 @home / v2.0'
for r in p(text, voice="af_heart"):
    for t in r.tokens:
        print(f"{t.text!r:<10} ws={t.whitespace!r:<4} start={t.start_ts!s:<7} end={t.end_ts!s:<7} ph={t.phonemes!r}")
