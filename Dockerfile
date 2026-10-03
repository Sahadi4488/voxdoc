# VoxDoc: one image serves the API and the built React app on one origin.
#   docker build -t voxdoc .
#   docker run --rm -p 7860:7860 --env-file backend/.env voxdoc    ->  http://localhost:7860

# ---------------------------------------------------------------- 1: build the frontend
# Node is only needed to build; none of it ends up in the final image.
FROM node:22-slim AS frontend
WORKDIR /frontend
# The package files first: the `npm ci` layer is reused until the dependencies change
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- 2: the app
FROM python:3.11-slim

# espeak-ng: Kokoro's fallback for words missing from its pronunciation dictionary
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run containers as user 1000: everything the app writes at
# runtime must belong to that user.
RUN useradd -m -u 1000 user
USER user
# HF_HOME is the same at build time (models downloaded into it) and at run time
# (models found there); if they differed, every start would download them again.
ENV HOME=/home/user \
    PATH=/home/user/venv/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /home/user/venv && mkdir -p /home/user/app
WORKDIR /home/user/app

# CPU-only torch from its own index, BEFORE the requirements: kokoro and
# sentence-transformers would otherwise pull the default Linux wheel, with CUDA.
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user backend/requirements.txt ./
RUN pip install -r requirements.txt

# Bake the models into the image: Kokoro, its 7 preset voices, MiniLM. Only the
# files the script imports are copied first, so editing the app later doesn't
# invalidate this layer and download ~400 MB again.
COPY --chown=user backend/app/__init__.py backend/app/config.py app/
COPY --chown=user backend/app/services/__init__.py backend/app/services/voices.py app/services/
COPY --chown=user backend/scripts/prefetch_models.py scripts/
RUN python scripts/prefetch_models.py
# From here on nothing is downloaded: a missing model fails loudly, never at a visitor's click
ENV HF_HUB_OFFLINE=1

COPY --chown=user backend/ ./
COPY --from=frontend --chown=user /frontend/dist ./frontend_dist
# Created here, owned by `user`, so a volume mounted on it inherits that ownership
RUN mkdir -p /home/user/app/data

ENV VOXDOC_DATA_DIR=/home/user/app/data \
    VOXDOC_FRONTEND_DIST=/home/user/app/frontend_dist \
    VOXDOC_WARM_TTS=true

EXPOSE 7860
# 7860: Hugging Face's default port. --proxy-headers: behind the host's reverse proxy,
# take the visitor's IP from X-Forwarded-For (the per-visitor question limit needs it).
# Trusting every proxy ("*") is safe only because the container is never exposed
# directly: on a VM it's bound to 127.0.0.1 behind Caddy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
