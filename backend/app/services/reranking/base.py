from typing import Protocol


class Reranker(Protocol):
    """Scores (query, document) pairs jointly. Higher means more relevant."""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """
        Score every document against the query, returning one float per document in input order.
        Synchronous and CPU/IO bound: callers run it inside ``asyncio.to_thread``.
        """
        ...
