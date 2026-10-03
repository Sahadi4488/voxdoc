# Running VoxDoc in production

## One origin, no CORS

The frontend only ever calls `/api/...` on its own origin. In development Vite's proxy
forwards those calls to FastAPI. In production FastAPI serves the built app itself:
`frontend/dist` is mounted at `/`, after the API routes. The backend has no CORS
middleware at all.

Without Docker, the production setup on one port (Windows, PowerShell, after the
"Run it locally" steps in the README):

```powershell
cd frontend; npm run build; cd ..\backend
$env:VOXDOC_WARM_TTS = "true"                  # load Kokoro at startup, not on the first Play
.venv\Scripts\python -m uvicorn app.main:app --port 8000   # http://127.0.0.1:8000
```

## Configuration

Environment variables or `backend/.env` (git-ignored), all prefixed `VOXDOC_`; see
`backend/.env.example` and `backend/app/config.py`. Without `VOXDOC_GROQ_API_KEY` the app
still runs: reading and audio work, and summaries and questions answer 503 "AI features
aren't configured on this server".

## Docker

One image serves the API and the built app on port 7860. The `Dockerfile` has two stages:
Node builds the frontend, then `python:3.11-slim` gets CPU-only torch, espeak-ng, the
requirements, and the Kokoro + MiniLM weights, downloaded at build time by
`backend/scripts/prefetch_models.py`. The container then runs with `HF_HUB_OFFLINE=1`, as
a non-root user (UID 1000).

```powershell
docker build -t voxdoc .
docker run --rm -p 7860:7860 --env-file backend/.env voxdoc   # http://localhost:7860
docker run --rm voxdoc ls -a                                  # must not list a .env
```

No Docker locally? `.github/workflows/docker.yml` builds and checks the image on GitHub on
every push: no `.env` in the image, cold start, the full flow
(`backend/scripts/container_check.py`), image size and peak RAM, on the run's summary page.
To test the AI features there too, add the repository secret `VOXDOC_GROQ_API_KEY`.

## Publishing

Pick the host from the measured peak RAM (`docs/measurements.md`). Either way the Groq key
is a runtime secret named `VOXDOC_GROQ_API_KEY`, never part of the image.

**Hugging Face Spaces (PRO, Docker SDK, CPU basic, public)**
1. Put this front matter at the very top of `README.md` (GitHub shows it as a small table):
   ```yaml
   ---
   title: VoxDoc
   sdk: docker
   app_port: 7860
   ---
   ```
2. In the Space's settings, add the secret `VOXDOC_GROQ_API_KEY`.
3. `git remote add space https://huggingface.co/spaces/<you>/voxdoc`, then
   `git push space master:main` (a write token as the password).
4. Watch the Logs tab, then open `https://<you>-voxdoc.hf.space`. The disk resets when the
   Space restarts, and it sleeps after 48 hours without visitors.

**A VM (student credits)**
1. Ubuntu, with at least the measured peak RAM + 1 GB; `curl -fsSL https://get.docker.com | sh`.
2. Clone the repo, create `.env` on the server, `docker build -t voxdoc .`
3. Run it bound to localhost only, with the data on a volume:
   ```bash
   docker run -d --restart unless-stopped -p 127.0.0.1:7860:7860 \
     -v voxdoc-data:/home/user/app/data --env-file .env voxdoc
   ```
4. Caddy for HTTPS; Caddyfile: `your.domain { reverse_proxy 127.0.0.1:7860 }` (a free
   DuckDNS subdomain works). The container trusts X-Forwarded-For only because nothing
   but Caddy can reach it.
5. Firewall: allow 22, 80 and 443 only. Documents now survive restarts, so the audio
   cache cap matters (`VOXDOC_AUDIO_CACHE_MAX_MB`, default 2048).
