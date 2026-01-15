from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectCreate, ProjectResponse
from app.core.database import get_db
from app.models.project import Project

from .shared_objects import router


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project.

    Creates a new project with the provided name and settings.
    The project starts in the UPLOAD stage.

    Args:
        project_in: Project creation request
        db: Database session dependency

    Returns:
        ProjectResponse: The created project

    Raises:
        HTTPException: If project creation fails
    """
    try:
        db_project = Project(
            name=project_in.name,
            active=project_in.active,
        )
        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        return ProjectResponse.model_validate(db_project)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create project: {e!s}",
        ) from e
