"""Get propagation status endpoint.

Provides the GET endpoint to retrieve the status of a propagation job.
"""

import uuid

from fastapi import HTTPException, status

from app.api.v1.schemas import PropagationStatusResponse

from .shared_objects import (
    propagation_jobs,
    router,
)

__all__ = ["get_propagation_status"]


@router.get("/projects/{project_id}/propagate/{job_id}", response_model=PropagationStatusResponse)
async def get_propagation_status(
    project_id: uuid.UUID,
    job_id: str,
) -> PropagationStatusResponse:
    """Get the status of a propagation job.

    Args:
        project_id: UUID of the project
        job_id: Job identifier

    Returns:
        PropagationStatusResponse with current job status

    Raises:
        HTTPException: If job not found
    """
    if job_id not in propagation_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Propagation job not found: {job_id}",
        )

    job = propagation_jobs[job_id]

    if job["project_id"] != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Propagation job {job_id} not found for project {project_id}",
        )

    return PropagationStatusResponse(
        job_id=job_id,
        project_id=project_id,
        status=job["status"],
        progress=job.get("progress"),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
    )
