"""Local sentence embeddings (all-MiniLM-L6-v2 by default).

The model loads lazily on first use, once per process (get_embedder is the
singleton and the FastAPI dependency tests override). Where the files live is
not hardcoded: Hugging Face's cache (HF_HOME) decides, so a Docker image can
download the model at build time.

Vectors are float32 and L2-normalised, so cosine similarity is a dot product.
"""
import threading
from functools import lru_cache

import numpy as np

from app.config import settings


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._load_lock = threading.Lock()
        self._encode_lock = threading.Lock()  # one encode at a time: it already uses every core

    @property
    def model(self):
        with self._load_lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # slow import, only when needed

                self._model = SentenceTransformer(self.model_name, device="cpu")
            return self._model

    @property
    def max_tokens(self) -> int:
        return self.model.max_seq_length

    def warm_up(self) -> None:
        _ = self.model

    def count_tokens(self, text: str) -> int:
        """Tokens the model sees for `text`, including [CLS] and [SEP]."""
        return len(self.model.tokenizer(text)["input_ids"])

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """(n, dim) float32, unit length."""
        with self._encode_lock:
            vecs = self.model.encode_document(texts, normalize_embeddings=True, batch_size=32,
                                              convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32).reshape(len(texts), -1)

    def embed_query(self, text: str) -> np.ndarray:
        """(dim,) float32, unit length."""
        with self._encode_lock:
            vec = self.model.encode_query(text, normalize_embeddings=True, convert_to_numpy=True,
                                          show_progress_bar=False)
        return np.asarray(vec, dtype=np.float32).reshape(-1)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Process-wide singleton; also the FastAPI dependency tests override."""
    return Embedder()


def to_blob(vec: np.ndarray) -> bytes:
    # Always float32 on disk: writing float64 and reading float32 would silently
    # give twice as many garbage numbers.
    return np.ascontiguousarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
