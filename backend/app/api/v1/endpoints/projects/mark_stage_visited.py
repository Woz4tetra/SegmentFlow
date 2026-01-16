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


@router.post("/projects/{project_id}/mark_stage_visited", response_model=ProjectResponse)
async def mark_stage_visited(
    project_id: UUID,
    stage: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Mark a stage as visited for a project.

    Updates the appropriate stage_visited flag when a user visits a stage.
    This is used to control stage navigation permissions.

    Args:
        project_id: ID of the project to update
        stage: Stage name to mark as visited (e.g., "upload", "trim", "manual_labeling")
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If project not found or invalid stage name
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Map stage name to visited field
        stage_field_map = {
            "upload": "upload_visited",
            "trim": "trim_visited",
            "manual_labeling": "manual_labeling_visited",
            "propagation": "propagation_visited",
            "validation": "validation_visited",
            "export": "export_visited",
        }

        if stage not in stage_field_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {stage}",
            )

        # Mark the stage as visited
        field_name = stage_field_map[stage]
        setattr(db_project, field_name, True)

        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        logger.info(f"Marked stage '{stage}' as visited for project {project_id}")
        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark stage as visited: {e!s}",
        ) from e
