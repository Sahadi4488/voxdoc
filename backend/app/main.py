"""VoxDoc API.  Run from backend/ (or anywhere):  fastapi dev app/main.py"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import documents, summaries, tts
from app.services import splitter
from app.services.embeddings import get_embedder
from app.services.llm import LLMBusy, LLMError
from app.services.tts_engine import get_tts_engine

# uvicorn configures only its own loggers: without a handler here, the app's
# INFO lines (Groq token usage per call) would be dropped.
_app_log = logging.getLogger("app")
if not _app_log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_log.addHandler(_handler)
    _app_log.setLevel(logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    splitter.warm_up()  # load spaCy now so the first upload isn't 3 s slower
    if settings.warm_tts:  # off by default: Kokoro takes seconds to load on every dev reload
        get_tts_engine().warm_up()
    if settings.warm_embedder:
        get_embedder().warm_up()
    yield


app = FastAPI(title="VoxDoc", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],  # cross-origin JS can't read it otherwise (the dev server)
)

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


app.include_router(documents.router)
app.include_router(summaries.router)
app.include_router(tts.router)
# config.py creates this folder: StaticFiles checks it here, at import time
app.mount("/audio", StaticFiles(directory=settings.audio_cache_dir), name="audio")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
