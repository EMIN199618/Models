"""Embedding modelləri (LangChain `Embeddings` interfeysi).

hashing — oflayn, deterministik: söz kökləri + simvol 4-qramları üzrə feature hashing.
  Azərbaycan dilinin şəkilçi zənginliyi üçün simvol n-qramları kökləri birləşdirir
  ("gömrüyü" ~ "gömrükdə"). Semantik sinonimləri tutmur — bu, real modelə keçid üçün
  ölçülən baza xəttidir (eval/run_eval.py retrieval precision/recall verir).
openai — `text-embedding-3-small`, `dimensions` sxemlə eyni ölçüdə.
"""
from __future__ import annotations

import hashlib
import math

from langchain_core.embeddings import Embeddings

from app.config import get_settings
from app.text import stem, tokens


class HashingEmbeddings(Embeddings):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def _h(self, s: str) -> tuple[int, float]:
        d = hashlib.blake2b(s.encode(), digest_size=8).digest()
        n = int.from_bytes(d, "big")
        return n % self.dim, (1.0 if (n >> 63) & 1 else -1.0)

    def _embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in tokens(text):
            i, sgn = self._h("w:" + stem(tok))
            v[i] += 1.0 * sgn
            padded = f"^{tok}$"
            for j in range(len(padded) - 3):
                i, sgn = self._h("c:" + padded[j:j + 4])
                v[i] += 0.35 * sgn
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


_emb: Embeddings | None = None


def get_embeddings() -> Embeddings:
    global _emb
    if _emb is None:
        s = get_settings()
        if s.embedding_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            _emb = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=s.embedding_dim)
        else:
            _emb = HashingEmbeddings(s.embedding_dim)
    return _emb
