"""App settings. Override any field with a VOXDOC_* env var or backend/.env,
e.g. VOXDOC_DATA_DIR=D:/voxdoc-data or VOXDOC_MAX_UPLOAD_MB=50.

Every path is anchored to the backend folder (never the current working
directory), so starting the server from anywhere uses the same database.
"""
from pathlib import Path

from pydantic import model_validator
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
    # Caps so one upload can't occupy the CPU for an hour on a public server
    max_pages: int = 150
    max_sentences: int = 3000
    # Vite dev server; the browser treats localhost and 127.0.0.1 as different origins
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Load Kokoro at startup instead of on the first /tts request. Off by default:
    # `fastapi dev` reloads on every save and would reload the model each time.
    warm_tts: bool = False

    @model_validator(mode="after")
    def _resolve_paths(self):
        # Relative paths from .env/env vars are relative to backend/, not the cwd
        self.data_dir = _anchor(self.data_dir)
        self.db_path = _anchor(self.db_path or self.data_dir / "voxdoc.db")
        self.upload_dir = _anchor(self.upload_dir or self.data_dir / "uploads")
        self.audio_cache_dir = _anchor(self.audio_cache_dir or self.data_dir / "audio_cache")
        # Must exist before app.main is imported: StaticFiles checks its
        # directory at mount time, before lifespan runs.
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def _anchor(p: Path) -> Path:
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


settings = Settings()
