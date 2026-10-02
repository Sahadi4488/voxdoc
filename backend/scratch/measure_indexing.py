"""Day 11 measurements on a real server process:
1. Time to first audio right after an upload, with background indexing on vs off.
2. Embedding time for the 15-page PDF.
3. RAM of the server process with Kokoro and MiniLM both loaded.

    python scratch\\measure_indexing.py
Uses its own data folder and port 8001; your data/ is untouched.
"""
import json
import os
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
PDF = BACKEND / "scratch/out/attention.pdf"  # 15 pages, 431 sentences
API = "http://127.0.0.1:8001"
TRIALS = 3
SENTENCE = 9  # ~20-word sentence


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.strip()


def server_pid():
    return int(ps("(Get-NetTCPConnection -LocalPort 8001 -State Listen).OwningProcess | Select-Object -First 1"))


def ram(pid):
    out = ps(f"$p=Get-Process -Id {pid}; '{{0}} {{1}}' -f $p.WorkingSet64, $p.PeakWorkingSet64")
    ws, peak = (int(x) / 2**30 for x in out.split())
    return ws, peak


def run(index_on_upload: bool):
    data = Path(tempfile.mkdtemp())
    env = {**os.environ, "VOXDOC_DATA_DIR": str(data), "VOXDOC_WARM_TTS": "true",
           "VOXDOC_INDEX_ON_UPLOAD": str(index_on_upload).lower(), "PYTHONWARNINGS": "ignore",
           "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"}
    proc = subprocess.Popen([str(BACKEND / ".venv/Scripts/fastapi.exe"), "run", "app/main.py", "--port", "8001"],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=API, timeout=300) as c:
            for _ in range(240):
                try:
                    if c.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.5)
            pid = server_pid()

            def upload():
                with open(PDF, "rb") as f:
                    return c.post("/documents", files={"file": ("attention.pdf", f, "application/pdf")}).json()

            def chunks(doc_id):
                con = sqlite3.connect(data / "voxdoc.db")
                n = con.execute("SELECT COUNT(*) FROM chunks c JOIN documents d ON d.id = c.doc_id WHERE d.public_id = ?",
                                (doc_id,)).fetchone()[0]
                con.close()
                return n

            # Warm-up (not measured): Kokoro is loaded at startup; this loads MiniLM too, if used
            warm = upload()
            c.post("/tts", json={"doc_id": warm["id"], "sentence_idx": 0, "voice": "presenter"})
            if index_on_upload:
                while chunks(warm["id"]) == 0:
                    time.sleep(0.2)

            first_audio, upload_s, index_s = [], [], []
            for _ in range(TRIALS):
                for f in (data / "audio_cache").glob("*"):
                    f.unlink()  # every trial synthesizes from scratch
                t0 = time.perf_counter()
                doc = upload()
                t1 = time.perf_counter()
                r = c.post("/tts", json={"doc_id": doc["id"], "sentence_idx": SENTENCE, "voice": "presenter"})
                t2 = time.perf_counter()
                assert r.status_code == 200 and not r.json()["cached"], r.text
                upload_s.append(t1 - t0)
                first_audio.append(t2 - t1)
                if index_on_upload:
                    while chunks(doc["id"]) == 0:
                        time.sleep(0.05)
                    index_s.append(time.perf_counter() - t1)
            ws, peak = ram(pid)
            return {"index_on_upload": index_on_upload, "upload_s": upload_s, "first_audio_s": first_audio,
                    "upload_to_chunks_s": index_s, "ram_gb": round(ws, 2), "peak_ram_gb": round(peak, 2)}
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


if __name__ == "__main__":
    if not PDF.exists():
        sys.exit(f"{PDF} missing (download the arXiv paper as on Day 3)")
    results = [run(False), run(True)]
    for r in results:
        print(json.dumps(r))
    off, on = (statistics.median(r["first_audio_s"]) for r in results)
    print(f"\nfirst audio after upload: {off:.2f} s without background indexing, {on:.2f} s with "
          f"({100 * (on - off) / off:+.0f}%)")
