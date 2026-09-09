from fastapi import APIRouter
from fastapi.responses import Response

from app.core.metrics import CONTENT_TYPE_LATEST, metrics_payload

router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose application metrics for Prometheus scraping."""
    return Response(content=metrics_payload(), media_type=CONTENT_TYPE_LATEST)
