"""POST /feedback — store a thumbs up/down on an answer (Phase 6 feedback loop)."""

from fastapi import APIRouter

from app.config import get_settings
from app.db.feedback_models import Feedback
from app.db.postgres import get_db_session
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.tracing import active_flags

router = APIRouter(tags=["Feedback"])


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
        config=active_flags(settings),
    )
    async with get_db_session() as session:
        session.add(row)
        await session.flush()
        return FeedbackResponse(id=row.id)
