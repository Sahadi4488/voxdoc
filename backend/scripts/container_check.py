"""Full-flow check and measurements against a running VoxDoc: the container, or a
local production run (uvicorn serving the built frontend).

    python backend/scripts/container_check.py http://localhost:7860

Standard library only, so it runs on a bare CI runner. Checks: the built app and
its JavaScript (with a JavaScript MIME type) at /, health, upload, audio for an
uncached sentence (time to first audio) in a US and a UK voice, the WAV itself,
a summary and a question with a citation (200 with a Groq key, 503 without),
and a JSON 404 for an unknown document. Exits 1 if any check fails.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "tests/fixtures/sample.docx"
US_GROWTH = "How much did the U.S. grow in 2024?"  # sentence 4: "...grew 3.5% in 2024."

failures = []


def check(name, ok, info=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({info})' if info else ''}", flush=True)
    if not ok:
        failures.append(name)


def call(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def post_json(url, payload):
    return call("POST", url, json.dumps(payload).encode(), {"Content-Type": "application/json"})


def multipart(field, filename, data):
    boundary = uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def main(base):
    api = f"{base}/api"
    metrics = {}

    status, _, page = call("GET", f"{base}/")
    check("built app served at /", status == 200 and b'id="root"' in page, status)
    script = re.search(rb'src="(/assets/[^"]+\.js)"', page)
    if script:
        status, headers, _ = call("GET", base + script[1].decode())
        check("its JavaScript has a JavaScript MIME type", status == 200 and "javascript" in headers["Content-Type"],
              headers["Content-Type"])
    else:
        check("index.html references a script", False)

    status, _, body = call("GET", f"{api}/health")
    health = json.loads(body)
    check("health: Kokoro loaded before the first visitor", status == 200 and health["tts_loaded"], health)

    started = time.perf_counter()
    status, _, body = call("POST", f"{api}/documents", *multipart("file", FIXTURE.name, FIXTURE.read_bytes()))
    metrics["upload_s"] = round(time.perf_counter() - started, 2)
    check("upload", status == 201, status)
    doc = json.loads(body)

    started = time.perf_counter()
    status, _, body = post_json(f"{api}/tts", {"doc_id": doc["id"], "sentence_idx": 1, "voice": "presenter"})
    tts = json.loads(body)
    status_wav, headers, wav = call("GET", base + tts.get("audio_url", ""))
    metrics["first_audio_s"] = round(time.perf_counter() - started, 2)  # request -> WAV downloaded
    check("audio for an uncached sentence", status == 200 and not tts["cached"] and tts["timings"], status)
    check("the WAV is served", status_wav == 200 and wav[:4] == b"RIFF", headers["Content-Type"])
    status, _, body = post_json(f"{api}/tts", {"doc_id": doc["id"], "sentence_idx": 1, "voice": "presenter"})
    check("the same sentence again is a cache hit", status == 200 and json.loads(body)["cached"])
    status, _, body = post_json(f"{api}/tts", {"doc_id": doc["id"], "sentence_idx": 2, "voice": "scholar"})
    check("a British voice works too", status == 200, status)

    expected = 200 if health["ai_configured"] else 503
    started = time.perf_counter()
    status, _, body = call("POST", f"{api}/documents/{doc['id']}/summary")
    metrics["summary_s"] = round(time.perf_counter() - started, 2)
    check(f"summary: {expected}", status == expected, body[:120])
    started = time.perf_counter()
    status, _, body = post_json(f"{api}/documents/{doc['id']}/ask", {"question": US_GROWTH})
    metrics["answer_s"] = round(time.perf_counter() - started, 2)
    check(f"question: {expected}", status == expected, body[:160])
    if status == 200:
        check("the answer cites the 3.5% sentence", 4 in json.loads(body)["citations"], body[:160])

    status, headers, body = call("GET", f"{api}/documents/nonsense")
    check("unknown document: JSON 404", status == 404 and "Document not found" in json.loads(body)["detail"])

    print(json.dumps(metrics))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:7860"))
