from __future__ import annotations

import hashlib
import os
from typing import Iterable

from backend.app.core.config import settings


def _hash_embedding(text: str, dim: int = 128) -> list[float]:
    vector = [0.0] * dim
    tokens = [t for t in text.lower().split() if t]
    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vector[idx] += 1.0
    return vector


def _normalize(v: list[float]) -> list[float]:
    norm = sum(x * x for x in v) ** 0.5
    if norm == 0:
        return v
    return [x / norm for x in v]


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    texts = [t or "" for t in texts]
    backend = os.getenv("EMBEDDINGS_BACKEND", settings.embeddings_backend).lower()
    if backend == "hash":
        return [_normalize(_hash_embedding(t)) for t in texts]
    if backend in {"openai", "auto"} and settings.openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.embeddings.create(
                model=settings.embeddings_model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception:
            if backend == "openai":
                return [_normalize(_hash_embedding(t)) for t in texts]

    if backend in {"sentence", "auto"}:
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            vectors = model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vectors]
        except Exception:
            if backend == "sentence":
                return [_normalize(_hash_embedding(t)) for t in texts]

    return [_normalize(_hash_embedding(t)) for t in texts]
