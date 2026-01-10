"""Label endpoints for CRUD operations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import LabelCreate, LabelResponse, LabelUpdate
from app.core.database import get_db
from app.models.label import Label
from app.models.project import Project

router = APIRouter()


@router.post(
    "/projects/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_label(
    project_id: UUID,
    label_in: LabelCreate,
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Create a new label for a project.

    Args:
        project_id: ID of the project to attach the label to
        label_in: Label creation payload
        db: Database session

    Returns:
        LabelResponse: The created label

    Raises:
        HTTPException: If project not found or creation fails
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    try:
        db_label = Label(
            project_id=project_id,
            name=label_in.name,
            color_hex=label_in.color_hex,
            thumbnail_path=label_in.thumbnail_path,
        )
        db.add(db_label)
        await db.commit()
        await db.refresh(db_label)
        return LabelResponse.model_validate(db_label)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create label: {e!s}",
        ) from e


@router.patch(
    "/labels/{label_id}",
    response_model=LabelResponse,
)
async def update_label(
    label_id: UUID,
    label_in: LabelUpdate,
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Update an existing label (partial update)."""
    # Fetch label
    result = await db.execute(select(Label).where(Label.id == label_id))
    db_label = result.scalar_one_or_none()
    if db_label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label with ID {label_id} not found",
        )

    try:
        update_data = label_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_label, field, value)
        db.add(db_label)
        await db.commit()
        await db.refresh(db_label)
        return LabelResponse.model_validate(db_label)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update label: {e!s}",
        ) from e
