"""VoxDoc API + the built frontend, on one origin.

Development:  fastapi dev app/main.py  (from backend/), with `npm run dev`, whose
              proxy sends /api to this server: same origin, so no CORS anywhere.
Production:   uvicorn app.main:app  serves /api/... and the built React app at /.
"""
import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import documents, qa, summaries, tts
from app.services import audio_cache, splitter
from app.services.embeddings import get_embedder
from app.services.llm import LLMBusy, LLMClient, LLMError, get_llm_client
from app.services.tts_engine import TTSEngine, get_tts_engine
from app.utils.rate_limit import RateLimited

# uvicorn configures only its own loggers: without a handler here, the app's
# INFO lines (Groq token usage per call) would be dropped.
_app_log = logging.getLogger("app")
if not _app_log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_log.addHandler(_handler)
    _app_log.setLevel(logging.INFO)
log = logging.getLogger(__name__)

# StaticFiles guesses types with `mimetypes`, which on Windows reads the registry,
# where .js is often text/plain. Browsers refuse to run a module script served
# that way, so the built app would be a blank page. Register them explicitly.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _remove_leftover_uploads()
    freed = audio_cache.prune_cache(settings.audio_cache_max_bytes)
    if freed:
        log.info("audio cache over its cap: removed %.1f MB of the oldest entries", freed / 2**20)
    splitter.warm_up()  # load spaCy now so the first upload isn't 3 s slower
    if settings.warm_tts:  # on in the container; off in dev, where every reload would reload Kokoro
        get_tts_engine().warm_up()
    if settings.warm_embedder:
        get_embedder().warm_up()
    yield


def _remove_leftover_uploads() -> None:
    """Uploads are deleted as soon as they're extracted; anything still there was
    left by a crash mid-upload (or by a version that kept the originals)."""
    if settings.upload_dir.is_dir():
        for f in settings.upload_dir.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)


app = FastAPI(title="VoxDoc", lifespan=lifespan)

MULTIPART_OVERHEAD = 64 * 1024


@app.middleware("http")
async def reject_oversized_bodies(request: Request, call_next):
    """413 before the body is read. The multipart parser spools the whole upload to
    disk before the route runs, so the route's own size check alone comes too late."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > settings.max_upload_bytes + MULTIPART_OVERHEAD:
        return JSONResponse({"detail": f"File too large: the limit is {settings.max_upload_mb} MB."}, 413)
    return await call_next(request)


@app.exception_handler(LLMError)
async def llm_error(request: Request, exc: LLMError):
    """The reason (str(exc), may quote Groq) goes to the log; the user gets public_message."""
    log.warning("%s on %s: %s", type(exc).__name__, request.url.path, exc)
    headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, LLMBusy) else None
    return JSONResponse({"detail": exc.public_message}, exc.status_code, headers=headers)


@app.exception_handler(RateLimited)
async def rate_limited(request: Request, exc: RateLimited):
    # "code" tells the UI this 429 is the visitor's own limit, not a busy Groq
    return JSONResponse({"detail": exc.message, "code": "rate_limited"}, 429,
                        headers={"Retry-After": str(exc.retry_after)})


api = APIRouter(prefix="/api")


@api.get("/health", tags=["meta"])
def health(engine: TTSEngine = Depends(get_tts_engine), llm: LLMClient = Depends(get_llm_client)):
    """Liveness for the host and the cold-start measurement. Never loads a model:
    it only reports whether Kokoro is loaded yet."""
    return {"status": "ok", "tts_loaded": engine.loaded, "ai_configured": llm.configured}


for router in (documents.router, qa.router, summaries.router, tts.router):
    api.include_router(router)
app.include_router(api)
# config.py creates this folder: StaticFiles checks it here, at import time
app.mount("/api/audio", StaticFiles(directory=settings.audio_cache_dir), name="audio")

# The built React app, mounted LAST: a mount at "/" matches every path, so placed
# before the API it would answer /api/... with 404s. Only when a build exists, so
# development without `npm run build` keeps working (Vite serves the frontend then).
if settings.frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="spa")
