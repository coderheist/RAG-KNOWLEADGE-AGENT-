"""
Semantic retrieval service (Phase 4).

Embeds a query using Gemini (RETRIEVAL_QUERY task type) and performs
an ANN search against the Qdrant collection.

Reuses the existing embed_texts() from Phase 2 — task_type is the only
difference between document ingestion and query embedding.
"""

import asyncio
import math
import time
from dataclasses import dataclass

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.db.qdrant import get_qdrant_client
from app.services import sparse
from app.services.embedding_service import embed_batch_with_retry
from app.services.fusion import reciprocal_rank_fusion
from app.services.reranking import get_reranker
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """A single chunk returned by the vector search."""

    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float   # cosine similarity (0 – 1)
    chunk_id: str = ""   # deterministic Qdrant point id (see vector_service.generate_point_id)
    rerank_score: float | None = None   # cross-encoder score, set only when reranking is enabled
    heading: str | None = None
    section: str | None = None


@dataclass
class _Hit:
    """A candidate in the hybrid pipeline, shaped like a Qdrant ScoredPoint for the shared downstream code."""

    id: str
    payload: dict
    score: float                       # dense cosine similarity
    rerank_score: float | None = None


async def _cosine_scores(client, coll: str, ids: list[str], query_vector: list[float]) -> dict[str, float]:
    """Dense cosine for candidates that only the sparse retriever found (they have no dense score yet)."""
    records = await client.retrieve(collection_name=coll, ids=ids, with_vectors=True, with_payload=False)
    q_norm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
    scores: dict[str, float] = {}
    for rec in records:
        vec = rec.vector
        if isinstance(vec, dict):
            vec = vec.get("") or next((v for v in vec.values() if isinstance(v, list)), None)
        if not vec:
            continue
        v_norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        scores[str(rec.id)] = sum(a * b for a, b in zip(query_vector, vec, strict=False)) / (q_norm * v_norm)
    return scores


async def _hybrid_candidates(
    client, coll: str, query: str, query_vector: list[float], top_k: int, settings
) -> list[_Hit]:
    """Dense (+ optional BM25) retrieval, Reciprocal Rank Fusion, then optional cross-encoder rerank."""
    n = top_k * settings.CANDIDATE_MULTIPLIER
    t0 = time.perf_counter()

    async def sparse_search() -> list:
        sparse_query = await sparse.embed_query(query)
        return await client.search(
            collection_name=coll,
            query_vector=qmodels.NamedSparseVector(name=sparse.SPARSE_VECTOR_NAME, vector=sparse_query),
            limit=n,
            with_payload=True,
        )

    dense_task = client.search(collection_name=coll, query_vector=query_vector, limit=n, with_payload=True)
    if settings.ENABLE_HYBRID_SEARCH:
        dense_hits, sparse_hits = await asyncio.gather(dense_task, sparse_search())
    else:
        dense_hits, sparse_hits = await dense_task, []
    t_search = time.perf_counter()

    payloads = {str(h.id): (h.payload or {}) for h in [*sparse_hits, *dense_hits]}
    dense_scores = {str(h.id): float(h.score) for h in dense_hits}
    dense_ids = [str(h.id) for h in dense_hits]
    if settings.ENABLE_HYBRID_SEARCH:
        rankings = [dense_ids, [str(h.id) for h in sparse_hits]]
        fused_ids = [i for i, _ in reciprocal_rank_fusion(rankings, settings.RRF_K)]
    else:
        fused_ids = dense_ids
    candidate_ids = fused_ids[: max(settings.RERANK_CANDIDATE_COUNT if settings.ENABLE_RERANKING else top_k, top_k)]

    missing = [i for i in candidate_ids if i not in dense_scores]
    if missing:
        dense_scores.update(await _cosine_scores(client, coll, missing, query_vector))
    hits = [_Hit(id=i, payload=payloads[i], score=dense_scores.get(i, 0.0)) for i in candidate_ids]
    t_fuse = time.perf_counter()

    if settings.ENABLE_RERANKING and hits:
        try:
            scores = await asyncio.to_thread(
                get_reranker().rerank, query, [h.payload.get("text", "") for h in hits]
            )
            for hit, score in zip(hits, scores, strict=True):
                hit.rerank_score = score
            hits.sort(key=lambda h: h.rerank_score if h.rerank_score is not None else float("-inf"), reverse=True)
        except Exception as exc:  # a reranker failure must degrade to the fused order, never break retrieval
            logger.warning("Reranking failed, keeping fused order: %s", exc)
    t_rerank = time.perf_counter()

    logger.info(
        "hybrid_retrieval: search=%.0fms fuse=%.0fms rerank=%.0fms candidates=%d hybrid=%s rerank=%s",
        (t_search - t0) * 1000, (t_fuse - t_search) * 1000, (t_rerank - t_fuse) * 1000, len(hits),
        settings.ENABLE_HYBRID_SEARCH, settings.ENABLE_RERANKING,
    )
    return hits[:top_k]


async def retrieve_chunks(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.0,
    collection_name: str | None = None,
) -> list[RetrievedChunk]:
    """
    Embed *query* and return the top-k most semantically similar chunks.

    Args:
        query:            Natural-language question from the user.
        top_k:            Maximum number of chunks to return.
        score_threshold:  Minimum cosine similarity to include a result.
                          Set to 0.0 to accept all results.
        collection_name:  Override the default collection from settings.

    Returns:
        List of RetrievedChunk, sorted by score descending.
    """
    settings = get_settings()
    client = get_qdrant_client()
    coll = collection_name or settings.QDRANT_COLLECTION

    # Embed the query with RETRIEVAL_QUERY task type (different from RETRIEVAL_DOCUMENT)
    vectors = await embed_batch_with_retry([query], task_type="RETRIEVAL_QUERY")
    query_vector = vectors[0]

    reordered = settings.ENABLE_HYBRID_SEARCH or settings.ENABLE_RERANKING
    if reordered:
        search_results = await _hybrid_candidates(client, coll, query, query_vector, top_k, settings)
    else:
        search_results = await client.search(
            collection_name=coll,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )

    # Log all raw candidate scores before filtering
    if search_results:
        logger.info("Raw candidate scores before filtering for query '%s':", query)
        for i, hit in enumerate(search_results):
            payload = hit.payload or {}
            filename = payload.get("filename", "unknown")
            logger.info("  Candidate #%d: filename='%s' score=%.4f", i+1, filename, hit.score)
    else:
        logger.info("No raw candidates returned from Qdrant search.")

    chunks: list[RetrievedChunk] = []
    
    if search_results:
        import uuid

        from sqlalchemy import select

        from app.db.models import Document
        from app.db.postgres import get_db_session
        
        doc_ids = set()
        for hit in search_results:
            payload = hit.payload or {}
            doc_id_str = payload.get("document_id")
            if doc_id_str:
                try:
                    doc_ids.add(uuid.UUID(doc_id_str))
                except ValueError:
                    pass
        
        valid_docs = set()
        if doc_ids:
            async with get_db_session() as session:
                from app.db.models import DocumentStatus
                res = await session.execute(
                    select(Document.id).where(
                        Document.id.in_(doc_ids),
                        Document.status == DocumentStatus.COMPLETED
                    )
                )
                valid_docs = {str(r[0]) for r in res}
                
        # First gather all valid chunks (excluding orphans)
        valid_candidates: list[RetrievedChunk] = []
        for hit in search_results:
            payload = hit.payload or {}
            doc_id_str = payload.get("document_id", "")
            if doc_id_str not in valid_docs:
                logger.warning("Found orphan vector referencing non-existent document_id=%s. Ignoring.", doc_id_str)
                continue
            valid_candidates.append(RetrievedChunk(
                document_id=doc_id_str,
                filename=payload.get("filename", "unknown"),
                page_number=int(payload.get("page_number", 1)),
                chunk_index=int(payload.get("chunk_index", 0)),
                text=payload.get("text", ""),
                score=float(hit.score),
                chunk_id=str(hit.id),
                rerank_score=getattr(hit, "rerank_score", None),
                heading=payload.get("heading"),
                section=payload.get("section"),
            ))

        if valid_candidates:
            # Dense-only results are ordered by cosine; fused/reranked results keep the pipeline's order.
            if not reordered:
                valid_candidates.sort(key=lambda c: c.score, reverse=True)
            top_score = max(c.score for c in valid_candidates)
            gap_cutoff = top_score - settings.RETRIEVAL_MAX_GAP
            logger.info(
                "Top score for query is %.4f. Gap threshold (max_gap=%.4f) cutoff is %.4f",
                top_score,
                settings.RETRIEVAL_MAX_GAP,
                gap_cutoff,
            )
            
            for c in valid_candidates:
                # Apply absolute score floor
                if c.score < settings.RETRIEVAL_MIN_SCORE:
                    logger.info(
                        "Filtering out chunk filename='%s' index=%d (score=%.4f < floor=%.2f)",
                        c.filename, c.chunk_index, c.score, settings.RETRIEVAL_MIN_SCORE
                    )
                    continue
                # Apply relative score gap limit
                if c.score < gap_cutoff:
                    logger.info(
                        "Filtering out chunk filename='%s' index=%d (score=%.4f < gap_cutoff=%.4f)",
                        c.filename, c.chunk_index, c.score, gap_cutoff
                    )
                    continue
                chunks.append(c)

    logger.info(
        "Retrieved %d chunks above threshold=%.3f (gap=%.3f) for query (top_k=%d)",
        len(chunks),
        settings.RETRIEVAL_MIN_SCORE,
        settings.RETRIEVAL_MAX_GAP,
        top_k,
    )
    return chunks
