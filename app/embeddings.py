"""Embedding abstraction.

Production uses sentence-transformers. Tests inject a deterministic fake.
Nothing downstream should import sentence_transformers directly.
"""
from __future__ import annotations

import hashlib
from typing import List, Protocol, Sequence

import numpy as np


class Embedder(Protocol):
    """Anything that turns text into fixed-width vectors."""

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        ...


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Rows of `a` against rows of `b` -> (len(a), len(b)) similarity matrix."""
    a = np.atleast_2d(a).astype(np.float64)
    b = np.atleast_2d(b).astype(np.float64)
    a_norm = np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = np.linalg.norm(b, axis=1, keepdims=True)
    # Guard against zero vectors producing nan.
    a_norm[a_norm == 0] = 1.0
    b_norm[b_norm == 0] = 1.0
    return (a / a_norm) @ (b / b_norm).T


class SentenceTransformerEmbedder:
    """Real embedder. Lazily loads the model so import stays cheap.

    `paraphrase-multilingual-MiniLM-L12-v2` is the right default here: bank
    narrations in India are frequently transliterated Hindi/Marathi, and the
    monolingual MiniLM handles those poorly.
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self._load().encode(list(texts)))


class HashingEmbedder:
    """Deterministic, dependency-free, offline embedder.

    Character 3-gram hashing into a fixed vector. This is NOT semantic --
    it captures surface similarity only. Two uses:
      1. Tests, where determinism matters more than meaning.
      2. A degraded fallback if the real model can't be loaded.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float64)
        t = f"  {text.lower().strip()}  "
        for i in range(len(t) - 2):
            gram = t[i : i + 3]
            h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        return v

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not len(texts):
            return np.empty((0, self.dim), dtype=np.float64)
        return np.vstack([self._vec(t) for t in texts])


class StubEmbedder:
    """Test double with hand-wired vectors. Raises on unknown input, so a test
    can never silently pass on a text the author forgot to define."""

    def __init__(self, table: dict[str, List[float]], dim: int | None = None):
        self.table = {k.lower(): np.asarray(v, dtype=np.float64) for k, v in table.items()}
        self.dim = dim or (len(next(iter(self.table.values()))) if self.table else 0)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not len(texts):
            return np.empty((0, self.dim), dtype=np.float64)
        out = []
        for t in texts:
            key = t.lower()
            if key not in self.table:
                raise KeyError(f"StubEmbedder has no vector for {t!r}. Add it to the table.")
            out.append(self.table[key])
        return np.vstack(out)
