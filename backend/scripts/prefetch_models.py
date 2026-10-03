"""Download every model VoxDoc uses into HF_HOME. The Dockerfile runs it at build time.

    python scripts/prefetch_models.py

Baked into the image, the models make a container start without a single
download: cold start is loading from disk, the first visitor never waits on a
~400 MB fetch, a restart on a host with an ephemeral disk doesn't fetch again,
and the app runs even when the Hugging Face Hub is down (the image sets
HF_HUB_OFFLINE=1 after this step, so anything missing fails at build time).

It does what TTSEngine and Embedder do at runtime: one shared KModel, one
KPipeline per accent, every preset voice (voices.py is the single source of
truth), one word synthesised per voice so G2P data is in place too, and MiniLM.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.services.voices import KOKORO_REPO, PRESETS, lang_code_for  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    from kokoro import KModel, KPipeline

    model = KModel(repo_id=KOKORO_REPO).to("cpu").eval()
    pipelines = {}
    for preset in PRESETS.values():
        lang = lang_code_for(preset.voice)
        if lang not in pipelines:
            pipelines[lang] = KPipeline(lang_code=lang, repo_id=KOKORO_REPO, model=model)
        pipe = pipelines[lang]
        pipe.load_voice(preset.voice)
        if not any(r.audio is not None for r in pipe("Hello.", voice=preset.voice)):
            sys.exit(f"{preset.voice}: Kokoro produced no audio")
        print(f"voice {preset.voice} ({preset.name}) ready", flush=True)

    from sentence_transformers import SentenceTransformer

    SentenceTransformer(settings.embedding_model, device="cpu").encode(["warm up"])
    print(f"{settings.embedding_model} ready")
    print(f"all models ready in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
