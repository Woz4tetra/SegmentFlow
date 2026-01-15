"""SAM3 model status and inference endpoints."""

from typing import Any

import torch
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.sam3_state import get_all_trackers, get_primary_tracker

router = APIRouter()


@router.get("/sam3/status", response_model=dict[str, Any])
async def sam3_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get SAM3 model status.

    Returns information about all SAM3 model instances including:
    - Whether models are loaded
    - Which GPUs are in use
    - Inference width configuration
    - Total number of available trackers for parallel propagation

    Args:
        db: Database session dependency

    Returns:
        dict: SAM3 status information

    Example response:
        {
            "initialized": true,
            "primary_gpu_id": 0,
            "num_trackers": 3,
            "available_gpus": [0, 1, 2],
            "trackers": [
                {
                    "gpu_id": 0,
                    "loaded": true,
                    "device": "cuda:0"
                },
                ...
            ],
            "inference_width": 960,
            "cuda_available": true
        }
    """
    sam3_tracker = get_primary_tracker()
    sam3_trackers = get_all_trackers()

    if not sam3_trackers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAM3 models not initialized. Check server logs for details.",
        )

    # Get info for each tracker
    trackers_info = [
        {
            "gpu_id": tracker.gpu_id,
            "loaded": tracker.model is not None,
            "device": str(tracker.device),
        }
        for tracker in sam3_trackers.values()
    ]

    return {
        "initialized": True,
        "primary_gpu_id": sam3_tracker.gpu_id if sam3_tracker else None,
        "num_trackers": len(sam3_trackers),
        "available_gpus": sorted(sam3_trackers.keys()),
        "trackers": trackers_info,
        "inference_width": settings.INFERENCE_WIDTH,
        "cuda_available": torch.cuda.is_available() if sam3_tracker else False,
    }
