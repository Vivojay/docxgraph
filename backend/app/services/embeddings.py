import hashlib
import math
import re

from ..config import settings

_EMBEDDER = None


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())


def normalize_vector(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0:
        return vec
    return [value / norm for value in vec]


def hash_embedding(text: str, dim: int = 256) -> list[float]:
    vec = [0.0 for _ in range(dim)]
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        value = (int.from_bytes(digest[5:9], "big") % 1000) / 1000.0
        vec[idx] += sign * value
    return normalize_vector(vec)


def select_embedding_provider() -> str:
    override = settings.embedding_provider.lower().strip()
    if override != "auto":
        return override
    if settings.openai_api_key:
        return "openai"
    return "hash"


class Embedder:
    def __init__(self, provider: str):
        self.provider = provider
        self._model = None
        self._client = None

    def _ensure_openai_client(self):
        if self._client:
            return
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)

    def _ensure_st_model(self):
        if self._model:
            return
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "openai" and settings.openai_api_key:
            self._ensure_openai_client()
            response = self._client.embeddings.create(model="text-embedding-3-small", input=texts)
            return [item.embedding for item in response.data]
        if self.provider == "sentence-transformers":
            try:
                self._ensure_st_model()
                vectors = self._model.encode(texts, normalize_embeddings=True)
                return [vector.tolist() for vector in vectors]
            except Exception:
                return [hash_embedding(text) for text in texts]
        return [hash_embedding(text) for text in texts]


def get_embedder() -> Embedder:
    global _EMBEDDER
    if not _EMBEDDER:
        _EMBEDDER = Embedder(select_embedding_provider())
    return _EMBEDDER
