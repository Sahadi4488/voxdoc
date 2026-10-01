"""Day 2 'done when' proofs for the audio cache.  Run from backend\\:
    python scratch\\cache_demo.py
"""
import time

from synth import audio_cache, cache_key, get_pipeline, speak

from app.config import settings

TEXT = "The cache stores audio together with its word timings."
VOICE = "af_heart"

get_pipeline("a")  # load the model up front so it isn't counted in the timings

# Start clean for this sentence so the first call is a guaranteed miss
for speed in (1, 1.05):
    for ext in ("wav", "json"):
        (settings.audio_cache_dir / f"{cache_key(TEXT, VOICE, speed)}.{ext}").unlink(missing_ok=True)


def timed(label, *args):
    t = time.perf_counter()
    wav, timings, hit = speak(*args)
    print(f"{label:<34} {'HIT ' if hit else 'MISS'}  {(time.perf_counter() - t) * 1000:8.1f} ms  "
          f"{len(timings)} words  {wav.name[:12]}...")
    return wav, timings, hit


print(f"Cache dir: {settings.audio_cache_dir}\n")
_, t1, h1 = timed("1. first call   (speed=1)", TEXT, VOICE, 1)
_, t2, h2 = timed("2. same again   (speed=1)", TEXT, VOICE, 1)
_, _, h3 = timed("3. speed=1.0", TEXT, VOICE, 1.0)
_, _, h4 = timed("4. speed=1.05", TEXT, VOICE, 1.05)

key = cache_key(TEXT, VOICE, 1)
(settings.audio_cache_dir / f"{key}.json").unlink()
print("   (deleted the .json sidecar for speed=1)")
print(f"5. get() after sidecar deleted      {'HIT' if audio_cache.get(key) else 'MISS'}")
_, _, h6 = timed("6. speak() regenerates", TEXT, VOICE, 1)

print("\nTimings survive a cache hit:", t1 == t2)
print("Sample timings:", t2[:3])

assert (h1, h2, h3, h4, h6) == (False, True, True, False, False) and audio_cache.get(key) and t1 == t2
print("\nAll cache checks passed.")
