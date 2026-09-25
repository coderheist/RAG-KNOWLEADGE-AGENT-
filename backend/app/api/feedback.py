"""POST /feedback — store a thumbs up/down on an answer (Phase 6 feedback loop)."""

from fastapi import APIRouter

from app.config import get_settings
from app.db.feedback_models import Feedback
from app.db.postgres import get_db_session
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["Feedback"])

_FLAGS = (
    "ENABLE_QUERY_REWRITE", "ENABLE_HYBRID_SEARCH", "ENABLE_RERANKING", "ENABLE_AGENTIC_LOOP",
    "ENABLE_GROUNDEDNESS_CHECK", "ENABLE_VERIFIED_CITATIONS", "GEMINI_MODEL",
)


@router.post("/feedback", response_model=FeedbackResponse, status_code=201, summary="Rate an answer")
async def create_feedback(body: FeedbackRequest) -> FeedbackResponse:
    settings = get_settings()
    row = Feedback(
        rating=body.rating,
        question=body.question,
        answer=body.answer,
        chunk_ids=body.chunk_ids,
        conversation_id=body.conversation_id,
        comment=(body.comment or "").strip() or None,
        config={flag: getattr(settings, flag, None) for flag in _FLAGS},
    )
    async with get_db_session() as session:
        session.add(row)
        await session.flush()
        return FeedbackResponse(id=row.id)
