"""Start propagation endpoint.

Provides the POST endpoint to start a label propagation job.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    PropagationJobResponse,
    PropagationRequest,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.project import Project

from .shared_objects import (
    analyze_propagation_segments,
    background_tasks,
    job_lock,
    job_websockets,
    propagation_jobs,
    router,
    run_propagation_job,
)

__all__ = ["start_propagation"]


@router.post("/projects/{project_id}/propagate", response_model=PropagationJobResponse)
async def start_propagation(
    project_id: uuid.UUID,
    request: PropagationRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> PropagationJobResponse:
    """Start a label propagation job for a project.

    Analyzes manually labeled frames and propagates labels to unlabeled frames
    using SAM3 video segmentation.

    Args:
        project_id: UUID of the project
        request: Optional propagation parameters
        db: Database session

    Returns:
        PropagationJobResponse with job details

    Raises:
        HTTPException: If project not found or no labeled frames
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    # Get max propagation length from request or config
    max_prop_length = settings.MAX_PROPAGATION_LENGTH
    if request and request.max_propagation_length:
        max_prop_length = request.max_propagation_length

    # Analyze segments
    segments, source_frames_data = await analyze_propagation_segments(
        project_id, db, max_prop_length
    )

    if not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No propagation segments found. Ensure at least one frame is manually labeled.",
        )

    if not source_frames_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No labeled points found on any frame.",
        )

    # Create job
    job_id = str(uuid.uuid4())
    total_frames = sum(seg.num_frames for seg in segments)

    async with job_lock:
        propagation_jobs[job_id] = {
            "job_id": job_id,
            "project_id": project_id,
            "status": "queued",
            "segments": segments,
            "total_segments": len(segments),
            "total_frames": total_frames,
            "progress": None,
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        job_websockets[job_id] = []

    # Start background task
    async def db_factory() -> AsyncGenerator[AsyncSession, None]:
        async for session in get_db():
            yield session

    task = asyncio.create_task(
        run_propagation_job(
            job_id,
            project_id,
            segments,
            source_frames_data,
            db_factory,
        )
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    return PropagationJobResponse(
        job_id=job_id,
        project_id=project_id,
        status="queued",
        total_segments=len(segments),
        total_frames=total_frames,
        message=f"Propagation job started with {len(segments)} segments and {total_frames} frames",
    )
