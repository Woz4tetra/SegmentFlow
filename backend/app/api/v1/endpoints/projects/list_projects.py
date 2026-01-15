from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectListResponse, ProjectResponse
from app.core.database import get_db
from app.models.project import Project

from .shared_objects import router


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """List all projects.

    Retrieves all projects sorted by most recently updated first.

    Args:
        db: Database session dependency

    Returns:
        ProjectListResponse: List of projects and total count

    Raises:
        HTTPException: If database query fails
    """
    try:
        # Query all projects ordered by updated_at descending
        result = await db.execute(
            select(Project).order_by(Project.updated_at.desc()),
        )
        projects = result.scalars().all()

        return ProjectListResponse(
            projects=[ProjectResponse.model_validate(p) for p in projects],
            total=len(projects),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {e!s}",
        ) from e
