from __future__ import annotations

import hashlib
import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    _shared_models: dict[str, SentenceTransformer] = {}
    _failed_models: set[str] = set()

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: Optional[SentenceTransformer] = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.array([], dtype=np.float32)
        model = self._get_model()
        if model:
            vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return np.asarray(vectors, dtype=np.float32)
        return np.vstack([self._fallback_vector(text) for text in texts])

    def cosine_similarity_matrix(self, vectors: np.ndarray) -> np.ndarray:
        if vectors.size == 0:
            return np.array([], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        safe = np.divide(vectors, np.maximum(norms, 1e-8))
        return np.clip(np.matmul(safe, safe.T), -1.0, 1.0)

    def _get_model(self) -> Optional[SentenceTransformer]:
        if self.settings.sentence_model_name in self._failed_models:
            return None
        if self._model is None:
            cached = self._shared_models.get(self.settings.sentence_model_name)
            if cached is not None:
                self._model = cached
                return self._model
            try:
                self._model = SentenceTransformer(self.settings.sentence_model_name)
                self._shared_models[self.settings.sentence_model_name] = self._model
            except Exception:
                logger.exception("Falling back to hashed embeddings", extra={"model_name": self.settings.sentence_model_name})
                self._failed_models.add(self.settings.sentence_model_name)
                return None
        return self._model

    def _fallback_vector(self, text: str, dims: int = 256) -> np.ndarray:
        tokens = [token.lower() for token in text.split() if token.strip()]
        vec = np.zeros(dims, dtype=np.float32)
        if not tokens:
            return vec
        for token in tokens:
            bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dims
            vec[bucket] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec
