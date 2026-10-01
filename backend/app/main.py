"""VoxDoc API.  Run from backend\\ (or anywhere):  fastapi dev app/main.py"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_db
from app.routers import documents
from app.services.splitter import warm_up


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    warm_up()  # load spaCy now so the first upload isn't 3 s slower
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


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
