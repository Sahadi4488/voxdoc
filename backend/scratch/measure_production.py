"""Day 14 on this machine, without Docker: the production setup the container runs
(uvicorn serving the built frontend, Kokoro loaded at startup, Hugging Face
offline), measured like the container would be. The GitHub Actions workflow
measures the real image.

    cd frontend && npm run build && cd ../backend
    python scratch\\measure_production.py

Own data folder and port 7860; your data/ is untouched. Reports cold start
(process start until /api/health answers), the full-flow check, and peak RAM.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
PORT = 7860


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.strip()


def main():
    if not (BACKEND.parent / "frontend/dist/index.html").exists():
        sys.exit("frontend/dist missing: run `npm run build` in frontend/ first")
    data = Path(tempfile.mkdtemp())
    env = {**os.environ, "VOXDOC_DATA_DIR": str(data), "VOXDOC_WARM_TTS": "true", "HF_HUB_OFFLINE": "1",
           "VOXDOC_GROQ_API_KEY": os.environ.get("VOXDOC_GROQ_API_KEY", ""), "PYTHONWARNINGS": "ignore",
           "HF_HUB_DISABLE_SYMLINKS_WARNING": "1", "PYTHONUTF8": "1",
           # = --forwarded-allow-ips "*" in the Dockerfile. As an argument, Windows (this
           # Python build too) expands "*" into the folder's file names; Linux exec form doesn't.
           "FORWARDED_ALLOW_IPS": "*"}
    log = open(data / "server.log", "w", encoding="utf-8")
    started = time.perf_counter()
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--proxy-headers"],
                            cwd=BACKEND, env=env, stdout=log, stderr=log)
    try:
        health = None
        while time.perf_counter() - started < 300 and proc.poll() is None:
            try:
                r = httpx.get(f"http://127.0.0.1:{PORT}/api/health", timeout=2)
                if r.status_code == 200:
                    health = r.json()
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        cold = time.perf_counter() - started
        print(f"cold start: {cold:.1f} s until /api/health answered {health}")
        if health is None:
            sys.exit(f"server didn't start; log: {data / 'server.log'}")
        check = subprocess.run([sys.executable, str(BACKEND / "scripts/container_check.py"), f"http://127.0.0.1:{PORT}"],
                               capture_output=True, text=True)
        print(check.stdout)
        pid = ps(f"(Get-NetTCPConnection -LocalPort {PORT} -State Listen).OwningProcess | Select-Object -First 1")
        ws, peak = (int(x) / 2**30 for x in ps(f"$p=Get-Process -Id {pid}; '{{0}} {{1}}' -f "
                                                "$p.WorkingSet64, $p.PeakWorkingSet64").split())
        print(json.dumps({"cold_start_s": round(cold, 1), "ram_gb": round(ws, 2), "peak_ram_gb": round(peak, 2)}))
        return check.returncode
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        log.close()


if __name__ == "__main__":
    sys.exit(main())
