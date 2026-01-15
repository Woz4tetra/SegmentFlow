from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectResponse
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.post("/projects/{project_id}/trim", response_model=ProjectResponse)
async def set_trim_range(
    project_id: UUID,
    trim_start: float,
    trim_end: float,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update the project's trim range with basic validation.

    Args:
        project_id: ID of the project
        trim_start: Start position in seconds
        trim_end: End position in seconds (must be greater than start)
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If project not found or validation fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        if trim_start < 0 or trim_end <= trim_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid trim range: ensure start >= 0 and end > start",
            )

        db_project.trim_start = trim_start
        db_project.trim_end = trim_end
        # Keep stage as TRIM; conversion/manual labeling will advance later
        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to set trim for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set trim range",
        ) from e
