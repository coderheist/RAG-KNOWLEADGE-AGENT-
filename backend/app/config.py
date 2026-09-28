"""
Application configuration using pydantic-settings.
All values are loaded from environment variables (or .env file).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "RAG Agent API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"         # development | staging | production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Google Gemini ──────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 3072          # gemini-embedding-001 output dimension
    EMBEDDING_BATCH_SIZE: int = 5          # chunks per embed API call

    # ── RAG retrieval ───────────────────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 5                # default chunks to retrieve per query
    RETRIEVAL_MIN_SCORE: float = 0.63        # minimum cosine similarity score threshold
    RETRIEVAL_MAX_GAP: float = 0.05          # maximum score difference from top score to keep a candidate
    MAX_HISTORY_PAIRS: int = 3             # conversation turns kept in context window

    # ── Query rewriting (Phase 2) ─────────────────────────────────────────────
    ENABLE_QUERY_REWRITE: bool = True        # measured: follow_up recall@5 0.300 -> 1.000, no other category regressed
    QUERY_REWRITE_MODEL: str = "gemini-flash-lite-latest"
    QUERY_REWRITE_HISTORY_TURNS: int = 3     # most recent user/assistant turns shown to the rewriter
    QUERY_REWRITE_MAX_TOKENS: int = 96

    # ── Hybrid search + reranking (Phase 3) — all off by default = old dense-only behaviour ──
    # dense + BM25 sparse merged with RRF. Measured: exact_term recall@5 0.583 -> 0.750, +4 ms. Only active on
    # collections that carry the sparse vector; older collections fall back to dense with a startup warning.
    ENABLE_HYBRID_SEARCH: bool = True
    ENABLE_RERANKING: bool = False           # cross-encoder rerank of the fused candidates
    INCLUDE_CHUNK_METADATA_IN_PROMPT: bool = False   # heading/section in each context block header
    SPARSE_MODEL: str = "Qdrant/bm25"
    RERANKER_PROVIDER: str = "local"
    RERANKER_MODEL: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    RERANK_CANDIDATE_COUNT: int = 20         # fused candidates handed to the cross-encoder
    RRF_K: int = 60
    CANDIDATE_MULTIPLIER: int = 4            # each retriever fetches top_k * this many candidates

    # ── Agentic graph (Phase 4) — off by default = the linear pipeline ────────────
    ENABLE_AGENTIC_LOOP: bool = False        # router + chunk grading with a capped retry loop + direct responses
    MAX_RETRIEVAL_LOOPS: int = 2             # hard cap on retries after the first retrieval (never unbounded)
    # Chunks graded *relevant* needed before generating without a retry. The spec's example is 2, but a
    # single-fact answer lives in one chunk, so 2 would retry nearly every such question.
    MIN_RELEVANT_CHUNKS: int = 1
    ENABLE_GROUNDEDNESS_CHECK: bool = False  # verify the finished answer against the retrieved chunks
    ENABLE_VERIFIED_CITATIONS: bool = False  # structured answer: claims with source ids validated server-side
    AGENT_MODEL: str = "gemini-flash-lite-latest"   # router / grader / groundedness checker
    AGENT_MAX_TOKENS: int = 512

    # ── Observability (Phase 6) ──────────────────────────────────────────────
    # USD per 1M tokens for the rag_llm_cost_usd_total metric. 0 = free tier; set from your plan's price sheet.
    LLM_PRICE_INPUT_PER_MTOK: float = 0.0
    LLM_PRICE_OUTPUT_PER_MTOK: float = 0.0
    # Langfuse tracing: off unless enabled AND both keys are set (self-hosted via docker-compose.observability.yml)
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_HOST: str = "http://langfuse:3000"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""

    # ── Embedding Resiliency ──────────────────────────────────────────────────
    MAX_EMBED_RETRIES: int = 5
    INITIAL_BACKOFF: float = 1.0
    MAX_BACKOFF: float = 16.0
    ENABLE_JITTER: bool = True
    MAX_CONCURRENT_EMBEDDINGS: int = 1


    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "raguser"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "ragdb"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        """Sync DSN used for health-check ping only."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Qdrant ─────────────────────────────────────────────────────────────────
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None        # optional; required for Qdrant Cloud
    QDRANT_COLLECTION: str = "documents"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # ── Upload limits ──────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50            # per-file size limit
    MAX_FILES_PER_UPLOAD: int = 10

    # ── PDF Chunking ────────────────────────────────────────────────────────────
    MIN_CHUNK_SIZE: int = 500              # target minimum chars per chunk
    MAX_CHUNK_SIZE: int = 2000             # max chars before recursive split
    CHUNK_OVERLAP: int = 200               # chars shared between consecutive chunks

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()  # type: ignore[call-arg]
