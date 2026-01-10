"""Projects endpoint for CRUD operations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.core.database import get_db
from app.models.project import Project

router = APIRouter()


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
