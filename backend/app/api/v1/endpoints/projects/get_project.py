from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectResponse
from app.core.database import get_db
from app.models.project import Project

from .shared_objects import router


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get a project by ID.

    Retrieves a specific project with all its details.

    Args:
        project_id: ID of the project to retrieve
        db: Database session dependency

    Returns:
        ProjectResponse: The requested project

    Raises:
        HTTPException: If project not found or query fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {e!s}",
        ) from e
