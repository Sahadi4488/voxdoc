import threading
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.tts_engine import get_tts_engine

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Every test gets its own database, uploads and audio cache; real data/ is never touched.
    Works because the app reads settings.* at call time, never at import time."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "audio_cache_dir", tmp_path / "audio_cache")
    monkeypatch.setattr(settings, "warm_tts", False)
    return tmp_path


class FakeEngine:
    """Stands in for Kokoro: 1 s of silence + two word timings. Records every call."""

    def __init__(self, delay: float = 0.0):
        self.lock = threading.RLock()
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


@pytest.fixture()
def client(fake_engine):
    app.dependency_overrides[get_tts_engine] = lambda: fake_engine
    try:
        with TestClient(app) as c:  # `with` runs the lifespan (init_db)
            yield c
    finally:
        app.dependency_overrides.clear()  # or later tests inherit the fake


def upload(client, path=None, name=None, content=None):
    data = content if content is not None else Path(path).read_bytes()
    return client.post("/documents", files={"file": (name or Path(path).name, data, "application/octet-stream")})


@pytest.fixture()
def docx_id(client):
    r = upload(client, FIXTURES / "sample.docx")
    assert r.status_code == 201, r.text
    return r.json()["id"]
