"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health", response_model=dict[str, Any])
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Health check endpoint.

    Verifies that:
    - The API server is running
    - The database connection is working

    Args:
        db: Database session dependency

    Returns:
        dict: Health status information

    Example response:
        {
            "status": "healthy",
            "service": "SegmentFlow",
            "version": "0.1.0",
            "database": "connected"
        }
    """
    # Test database connection
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_status,
    }


@router.get("/", response_model=dict[str, str])
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        dict: Welcome message
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "docs": "/docs",
    }
