from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectResponse, ProjectUpdate
from app.core.database import get_db
from app.models.project import Project

from .shared_objects import router


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update a project.

    Updates one or more fields of an existing project.
    Only provided fields are updated.

    Args:
        project_id: ID of the project to update
        project_in: Project update request with fields to update
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If project not found or update fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Update only provided fields
        update_data = project_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_project, field, value)

        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update project: {e!s}",
        ) from e
