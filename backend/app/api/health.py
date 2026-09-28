"""Liveness/readiness endpoint used by docker-compose, deploys and the frontend start page."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "unavailable"]


@router.get("/health")
async def health(
    response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database is unavailable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="error", database="unavailable")
    return HealthResponse(status="ok", database="ok")
