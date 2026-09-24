from functools import lru_cache

from app.config import get_settings
from app.services.reranking.base import Reranker
from app.services.reranking.local import LocalReranker


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    """Return the configured reranker. The model is loaded lazily on first use and then reused."""
    settings = get_settings()
    if settings.RERANKER_PROVIDER == "local":
        return LocalReranker(settings.RERANKER_MODEL)
    raise ValueError(f"Unsupported RERANKER_PROVIDER {settings.RERANKER_PROVIDER!r} (supported: 'local')")
