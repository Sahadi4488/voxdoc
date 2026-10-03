"""App settings. Override any field with a VOXDOC_* env var or backend/.env,
e.g. VOXDOC_DATA_DIR=D:/voxdoc-data or VOXDOC_MAX_UPLOAD_MB=50.

Every path is anchored to the backend folder (never the current working
directory), so starting the server from anywhere uses the same database.
"""
from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # An absolute env_file path too: a relative ".env" is looked up in the cwd
    model_config = SettingsConfigDict(env_prefix="VOXDOC_", env_file=BACKEND_DIR / ".env", extra="ignore")

    data_dir: Path = BACKEND_DIR / "data"
    db_path: Path | None = None  # default: data_dir/voxdoc.db
    upload_dir: Path | None = None  # default: data_dir/uploads
    audio_cache_dir: Path | None = None  # default: data_dir/audio_cache
    max_upload_mb: int = 20
    # Disk cap for synthesized audio: past it, the least recently used entries go (down to 80%)
    audio_cache_max_mb: int = 2048
    # The built React app (npm run build), served at / when the folder exists
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"
    # Caps so one upload can't occupy the CPU for an hour on a public server
    max_pages: int = 150
    max_sentences: int = 3000
    # Load Kokoro at startup instead of on the first /tts request. Off by default:
    # `fastapi dev` reloads on every save and would reload the model each time.
    warm_tts: bool = False
    # Retrieval (Day 11). Changing the model re-indexes documents on their next question.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Embed a document in the background right after upload, or lazily on its first question.
    # Off: measured on Day 11, background indexing slowed the first audio after an upload by
    # 35% (3.52 s -> 4.77 s, 15-page PDF), over the 30% limit. The demo moment comes first.
    index_on_upload: bool = False
    # Load MiniLM at startup, so the first question only waits for embedding (~2 s / 15 pages)
    warm_embedder: bool = False
    # Groq (Day 12). SecretStr: printing settings or a traceback shows '**********', never the
    # key. Without a key the reader and audio still work; the AI endpoints answer 503.
    groq_api_key: SecretStr | None = None
    # Separate models: Groq's free-plan limits are per model, so summaries and Q&A don't
    # use up each other's tokens-per-minute budget.
    groq_summary_model: str = "openai/gpt-oss-20b"
    groq_qa_model: str = "openai/gpt-oss-120b"
    # Q&A (Day 13). A question whose best chunk scores below this gets "not found" without
    # a Groq call. Day 11 eval with the real MiniLM: off-topic questions topped out at
    # 0.166, on-topic ones started at 0.277.
    qa_min_score: float = 0.22
    # Questions per visitor (IP address) per window; in memory, so per process
    qa_rate_limit: int = 10
    qa_rate_window_s: int = 600

    @field_validator("groq_api_key")
    @classmethod
    def _blank_key_is_no_key(cls, v: SecretStr | None) -> SecretStr | None:
        # VOXDOC_GROQ_API_KEY= (copied from .env.example unfilled) means "not configured"
        return v if v is not None and v.get_secret_value().strip() else None

    @model_validator(mode="after")
    def _resolve_paths(self):
        # Relative paths from .env/env vars are relative to backend/, not the cwd
        self.data_dir = _anchor(self.data_dir)
        self.db_path = _anchor(self.db_path or self.data_dir / "voxdoc.db")
        self.upload_dir = _anchor(self.upload_dir or self.data_dir / "uploads")
        self.audio_cache_dir = _anchor(self.audio_cache_dir or self.data_dir / "audio_cache")
        self.frontend_dist = _anchor(self.frontend_dist)
        # Must exist before app.main is imported: StaticFiles checks its
        # directory at mount time, before lifespan runs.
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def audio_cache_max_bytes(self) -> int:
        return self.audio_cache_max_mb * 1024 * 1024


def _anchor(p: Path) -> Path:
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


settings = Settings()
