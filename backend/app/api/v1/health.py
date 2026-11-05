import asyncio
import logging
from contextlib import suppress

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, str]:
    """Liveness probe: verifies that the application process is running."""
    return {"status": "alive", "version": settings.VERSION}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Readiness probe: verifies that the application can communicate with downstream services."""
    database_ok = False
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
        database_ok = True
    except Exception as exc:
        with suppress(Exception):
            await db.rollback()
        logger.error("Database connection readiness probe failed: %s", exc)

    status_code = status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if database_ok else "unhealthy",
            "database": database_ok,
            "version": settings.VERSION,
        },
    )
