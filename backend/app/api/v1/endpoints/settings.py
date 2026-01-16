"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/settings", response_model=dict[str, Any])
async def get_app_settings() -> dict[str, Any]:
    """Get application settings relevant to the frontend.

    Returns configuration values that the frontend needs, such as
    navigation settings and display options.

    Returns:
        dict: Frontend-relevant configuration values

    Example response:
        {
            "big_jump_size": 500,
            "max_propagation_length": 1000,
            "mask_transparency": 0.5
        }
    """
    return {
        "big_jump_size": settings.BIG_JUMP_SIZE,
        "max_propagation_length": settings.MAX_PROPAGATION_LENGTH,
        "mask_transparency": settings.MASK_TRANSPARENCY,
    }
