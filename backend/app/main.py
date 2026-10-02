"""VoxDoc API.  Run from backend/ (or anywhere):  fastapi dev app/main.py"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import documents, tts
from app.services import splitter
from app.services.embeddings import get_embedder
from app.services.tts_engine import get_tts_engine


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


app.include_router(documents.router)
app.include_router(tts.router)
# config.py creates this folder: StaticFiles checks it here, at import time
app.mount("/audio", StaticFiles(directory=settings.audio_cache_dir), name="audio")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
