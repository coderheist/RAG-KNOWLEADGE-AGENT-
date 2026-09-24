"""
Sparse (BM25) text embeddings via fastembed (Phase 3).

Runs locally on CPU and costs nothing: no external API. Sparse vectors capture exact-token
matches (product codes, error codes, surnames, dates) that dense embeddings blur together.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from qdrant_client.http import models as qmodels

from app.config import get_settings

SPARSE_VECTOR_NAME = "bm25"


@lru_cache(maxsize=1)
def _model() -> Any:
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name=get_settings().SPARSE_MODEL)


def _to_qdrant(embedding: Any) -> qmodels.SparseVector:
    return qmodels.SparseVector(indices=embedding.indices.tolist(), values=embedding.values.tolist())


def embed_documents_sync(texts: list[str]) -> list[qmodels.SparseVector]:
    return [_to_qdrant(e) for e in _model().embed(texts)]


def embed_query_sync(text: str) -> qmodels.SparseVector:
    return _to_qdrant(next(iter(_model().query_embed(text))))


async def embed_documents(texts: list[str]) -> list[qmodels.SparseVector]:
    return await asyncio.to_thread(embed_documents_sync, texts)


async def embed_query(text: str) -> qmodels.SparseVector:
    return await asyncio.to_thread(embed_query_sync, text)
