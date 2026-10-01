import re
import threading

import pytest

from app.services.tts_engine import get_or_create_audio
from tests.conftest import FakeEngine


def tts(client, doc_id, idx=0, voice="presenter", **extra):
    return client.post("/tts", json={"doc_id": doc_id, "sentence_idx": idx, "voice": voice, **extra})


def test_voices_lists_seven_presets(client):
    presets = client.get("/voices").json()
    assert len(presets) == 7
    assert {"presenter", "scholar"} <= {p["id"] for p in presets}


def test_tts_generates_then_hits_cache(client, docx_id, fake_engine, isolated_data):
    r = tts(client, docx_id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cached"] is False and body["duration"] == 1.0
    assert re.fullmatch(r"/audio/[0-9a-f]{64}\.wav", body["audio_url"])
    assert [t["word"] for t in body["timings"]] == ["Hello", "world."]
    key = body["audio_url"].rsplit("/", 1)[1]
    assert (isolated_data / "audio_cache" / key).exists()

    again = tts(client, docx_id).json()
    assert again["cached"] is True and again["audio_url"] == body["audio_url"]
    assert again["timings"] == body["timings"] and again["duration"] == 1.0
    assert len(fake_engine.calls) == 1


def test_tts_uses_kokoro_voice_and_preset_default_speed(client, docx_id, fake_engine):
    tts(client, docx_id, voice="calm")  # af_nicole, default speed 0.9
    tts(client, docx_id, voice="scholar", speed=1.2)
    assert [(v, s) for _, v, s in fake_engine.calls] == [("af_nicole", 0.9), ("bm_george", 1.2)]
    assert fake_engine.calls[0][0] == "VoxDoc Test Document"  # sentence 0 of the DOCX


def test_speed_1_and_1_0_share_audio(client, docx_id, fake_engine):
    assert tts(client, docx_id, speed=1).json()["cached"] is False
    assert tts(client, docx_id, speed=1.0).json()["cached"] is True
    assert tts(client, docx_id, speed=1.05).json()["cached"] is False


def test_unknown_document_404(client):
    r = tts(client, 9999)
    assert r.status_code == 404 and r.json()["detail"] == "Document 9999 not found."


def test_sentence_out_of_range_404(client, docx_id):
    r = tts(client, docx_id, idx=17)
    assert r.status_code == 404 and "sentences 0-16" in r.json()["detail"]


def test_unknown_preset_422(client, docx_id):
    r = tts(client, docx_id, voice="af_heart")  # Kokoro ids are not accepted, only presets
    assert r.status_code == 422 and "Valid presets" in r.json()["detail"]


@pytest.mark.parametrize("payload", [{"speed": 3.0}, {"speed": 0.49}, {"sentence_idx": -1}])
def test_invalid_request_422(client, docx_id, payload):
    body = {"doc_id": docx_id, "sentence_idx": 0, "voice": "presenter", **payload}
    assert client.post("/tts", json=body).status_code == 422


def test_concurrent_requests_synthesize_once(isolated_data):
    """Play + prefetch of the same sentence at the same moment -> one synthesis."""
    engine = FakeEngine(delay=0.2)
    results = []
    threads = [threading.Thread(target=lambda: results.append(
        get_or_create_audio(engine, "Same sentence.", "af_heart", 1.0))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(engine.calls) == 1
    assert sorted(r.cached for r in results) == [False, True, True, True]
