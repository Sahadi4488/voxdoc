"""Day 14 production wiring: /api prefix, health, same origin (no CORS), the built
frontend served by FastAPI, uploads not kept."""
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.tts_engine import get_tts_engine
from tests.conftest import FIXTURES, upload

BACKEND = Path(__file__).resolve().parents[1]


def test_health_reports_without_loading_models(client):
    app.dependency_overrides.pop(get_tts_engine)  # the real, lazy engine
    get_tts_engine.cache_clear()
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "tts_loaded": False, "ai_configured": True}
    assert get_tts_engine()._model is None  # asking didn't load Kokoro
    get_tts_engine.cache_clear()


def test_no_cors_headers(client, docx_id):
    """Same origin in dev (Vite proxy) and production: no CORS middleware at all."""
    r = client.get(f"/api/documents/{docx_id}", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers
    pre = client.options("/api/tts", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in pre.headers


def test_audio_is_served_under_api(client, docx_id):
    url = client.post("/api/tts", json={"doc_id": docx_id, "sentence_idx": 0, "voice": "presenter"}).json()["audio_url"]
    r = client.get(url)
    assert url.startswith("/api/audio/") and r.status_code == 200 and r.content[:4] == b"RIFF"


def test_failed_upload_leaves_no_file(client, isolated_data):
    r = upload(client, FIXTURES / "scanned.pdf")
    assert r.status_code == 422
    assert not any((isolated_data / "uploads").glob("*"))


def test_leftover_uploads_are_removed_at_startup(isolated_data):
    uploads = isolated_data / "uploads"
    uploads.mkdir()
    (uploads / "0123abcd.pdf").write_bytes(b"left by a crash")
    with TestClient(app):
        pass
    assert not any(uploads.iterdir())


def test_startup_prunes_the_audio_cache(isolated_data, monkeypatch, fake_engine):
    from app.services.tts_engine import get_or_create_audio
    get_or_create_audio(fake_engine, "A sentence.", "af_heart", 1.0)
    assert any((isolated_data / "audio_cache").iterdir())
    monkeypatch.setattr(settings, "audio_cache_max_mb", 0)
    with TestClient(app):
        pass
    assert not any((isolated_data / "audio_cache").iterdir())


SERVE = """
import json, sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    out = {}
    for path in ["/", "/?doc=abc", "/assets/app.js", "/api/health", "/api/documents/nope"]:
        r = c.get(path)
        out[path] = [r.status_code, r.headers.get("content-type", ""), r.text[:200]]
print(json.dumps(out))
"""


def serve(tmp_path, dist):
    """Import the app in a fresh process: the frontend mount is decided at import."""
    env = {**os.environ, "VOXDOC_FRONTEND_DIST": str(dist), "VOXDOC_DATA_DIR": str(tmp_path / "data"),
           "VOXDOC_GROQ_API_KEY": "", "PYTHONWARNINGS": "ignore"}
    r = subprocess.run([sys.executable, "-c", SERVE], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_built_frontend_is_served_after_the_api(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root>VOXDOC_INDEX</div>")
    (dist / "assets" / "app.js").write_text("console.log('app')")
    out = serve(tmp_path, dist)
    assert out["/"][0] == 200 and "VOXDOC_INDEX" in out["/"][2]
    assert out["/?doc=abc"][0] == 200 and "VOXDOC_INDEX" in out["/?doc=abc"][2]  # the app reads ?doc itself
    assert out["/assets/app.js"][0] == 200 and "javascript" in out["/assets/app.js"][1]
    # The API still answers, not the "/" mount
    assert out["/api/health"][0] == 200 and json.loads(out["/api/health"][2])["status"] == "ok"
    assert out["/api/documents/nope"][0] == 404 and "Document not found" in out["/api/documents/nope"][2]


def test_without_a_build_the_api_still_works(tmp_path):
    out = serve(tmp_path, tmp_path / "no-such-dist")
    assert out["/"][0] == 404  # nothing mounted at /: development uses Vite instead
    assert out["/api/health"][0] == 200
