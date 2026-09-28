"""
Health API router.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.schemas.health import HealthResponse
from app.services.health_service import get_health

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description=(
        "Returns the connectivity status for Gemini, PostgreSQL, and Qdrant. "
        "Overall `status` is `ok` only when all services are reachable."
    ),
)
async def health_check() -> HealthResponse:
    return await get_health()


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint (see docker-compose.observability.yml)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
