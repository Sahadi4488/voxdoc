import json
import re
import time
import zlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.routers.qa import get_question_limiter
from app.services.embeddings import get_embedder
from app.services.llm import LLMClient, get_llm_client
from app.services.tts_engine import get_tts_engine

FIXTURES = Path(__file__).parent / "fixtures"
# Read before any fixture blanks it: only the live `groq` tests may use the real key
REAL_GROQ_KEY = settings.groq_api_key


def _audio_files():
    """The /api/audio mount. StaticFiles fixes its folder at import time: the one place the
    app doesn't read settings at call time."""
    return next(r.app for r in app.routes if getattr(r, "name", None) == "audio")


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Every test gets its own database, uploads and audio cache; real data/ is never touched.
    Works because the app reads settings.* at call time, never at import time, except for
    the /api/audio mount, which is pointed at the test's cache here."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "audio_cache_dir", tmp_path / "audio_cache")
    # Without this, GET /api/audio/... read the real data/audio_cache: a test passed only
    # because a WAV with the same key happened to be there (a fresh clone has none)
    monkeypatch.setattr(_audio_files(), "all_directories", [tmp_path / "audio_cache"])
    monkeypatch.setattr(settings, "warm_tts", False)
    monkeypatch.setattr(settings, "warm_embedder", False)
    # A key in backend/.env must never reach the tests: no test spends real quota by accident
    monkeypatch.setattr(settings, "groq_api_key", None)
    get_llm_client.cache_clear()
    get_question_limiter.cache_clear()  # every test starts with a fresh per-visitor limit
    yield tmp_path
    get_llm_client.cache_clear()
    get_question_limiter.cache_clear()


class FakeEngine:
    """Stands in for Kokoro: 1 s of silence + two word timings. Records every call."""

    loaded = False  # what GET /api/health reports

    def __init__(self, delay: float = 0.0):
        self.calls: list[tuple[str, str, float]] = []
        self.delay = delay

    def synthesize(self, text, kokoro_voice, speed):
        self.calls.append((text, kokoro_voice, speed))
        time.sleep(self.delay)
        return np.zeros(24000, dtype=np.float32), [
            {"word": "Hello", "start": 0.1, "end": 0.5},
            {"word": "world.", "start": 0.5, "end": 0.9},
        ]


@pytest.fixture()
def fake_engine():
    return FakeEngine()


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts that share words score higher.
    Tokens = words + [CLS]/[SEP]. Records every embed call."""

    model_name = "fake-bow"
    max_tokens = 256
    dim = 64

    def __init__(self):
        self.document_calls = 0

    def count_tokens(self, text):
        return len(text.split()) + 2

    def _vec(self, text):
        v = np.zeros(self.dim, dtype=np.float32)
        for w in re.findall(r"[a-z0-9.%]+", text.lower()):
            v[zlib.crc32(w.encode()) % self.dim] += 1
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts):
        self.document_calls += 1
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture()
def fake_embedder():
    return FakeEmbedder()


SUMMARY = {"overview": "A short test document about reading aloud.",
           "key_points": ["VoxDoc reads documents aloud.", "It highlights each word."]}


class FakeGroq:
    """Stands in for groq.Groq. Answers from a script, one reply per request; the
    last reply repeats. A reply is a dict (sent as JSON), a raw string, a
    (content, finish_reason) tuple, or an exception to raise. Records requests."""

    def __init__(self, *replies, delay: float = 0.0):
        self.replies = list(replies) or [SUMMARY]
        self.delay = delay
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        time.sleep(self.delay)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        content, finish_reason = reply if isinstance(reply, tuple) else (reply, "stop")
        if isinstance(content, dict):
            content = json.dumps(content)
        prompt = kwargs["messages"][0]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)],
            usage=SimpleNamespace(prompt_tokens=len(prompt) // 4, completion_tokens=100,
                                  completion_tokens_details=SimpleNamespace(reasoning_tokens=40)),
        )


@pytest.fixture()
def fake_groq():
    return FakeGroq()


@pytest.fixture()
def client(fake_engine, fake_embedder, fake_groq):
    app.dependency_overrides[get_tts_engine] = lambda: fake_engine
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    llm = LLMClient(SecretStr("test-key"), client=fake_groq)
    app.dependency_overrides[get_llm_client] = lambda: llm
    try:
        with TestClient(app) as c:  # `with` runs the lifespan (init_db)
            yield c
    finally:
        app.dependency_overrides.clear()  # or later tests inherit the fake


def upload(client, path=None, name=None, content=None):
    data = content if content is not None else Path(path).read_bytes()
    return client.post("/api/documents", files={"file": (name or Path(path).name, data, "application/octet-stream")})


@pytest.fixture()
def docx_id(client):
    r = upload(client, FIXTURES / "sample.docx")
    assert r.status_code == 201, r.text
    return r.json()["id"]
