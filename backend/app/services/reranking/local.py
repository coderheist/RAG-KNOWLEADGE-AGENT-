"""Local cross-encoder reranker (fastembed / ONNX, CPU). No API key, no per-query cost."""

from __future__ import annotations

from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


class LocalReranker:
    """Cross-encoder scoring of (query, chunk) pairs, e.g. ``Xenova/ms-marco-MiniLM-L-6-v2``."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            logger.info("Loading cross-encoder reranker %s", self.model_name)
            self._model = TextCrossEncoder(model_name=self.model_name)
        return self._model

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        return [float(score) for score in self._load().rerank(query, documents)]
