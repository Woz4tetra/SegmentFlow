"""Label endpoints for CRUD operations."""

from uuid import UUID

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import LabelCreate, LabelResponse, LabelUpdate
from app.core.database import get_db
from app.core.config import settings
from app.models.label import Label
from app.models.project import Project

router = APIRouter()

@router.get(
    "/projects/{project_id}/labels",
    response_model=list[LabelResponse],
)
async def list_labels(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[LabelResponse]:
    """List all labels for a project.

    Args:
        project_id: ID of the project
        db: Database session

    Returns:
        list[LabelResponse]: List of labels for the project

    Raises:
        HTTPException: If project not found
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    # Fetch labels
    label_result = await db.execute(select(Label).where(Label.project_id == project_id))
    labels = label_result.scalars().all()
    return [LabelResponse.model_validate(l) for l in labels]


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


@router.post(
    "/labels/{label_id}/thumbnail",
)
async def upload_label_thumbnail(
    label_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Upload and set a thumbnail image for a label.

    Saves the uploaded file into the project's storage directory under
    `label_thumbs/{label_id}.ext` and updates the label's `thumbnail_path`.

    Returns the updated label response.
    """
    # Fetch label to determine project and validate existence
    result = await db.execute(select(Label).where(Label.id == label_id))
    db_label = result.scalar_one_or_none()
    if db_label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label with ID {label_id} not found",
        )

    # Ensure project exists (and get its id)
    proj_result = await db.execute(select(Project).where(Project.id == db_label.project_id))
    project = proj_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {db_label.project_id} not found",
        )

    # Prepare destination directory and file path
    root = Path(settings.PROJECTS_ROOT_DIR)
    project_dir = root / str(db_label.project_id)
    thumbs_dir = project_dir / "label_thumbs"
    try:
        thumbs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare thumbnail directory: {e!s}",
        ) from e

    # Determine extension from uploaded filename (fallback to .png)
    original_name = file.filename or "thumbnail.png"
    ext = Path(original_name).suffix.lower() or ".png"
    # Only allow common image types
    if ext not in {".png", ".jpg", ".jpeg"}:
        ext = ".png"
    dest_path = thumbs_dir / f"{label_id}{ext}"

    # Save file
    try:
        contents = await file.read()
        dest_path.write_bytes(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save thumbnail: {e!s}",
        ) from e

    # Update label thumbnail_path to served route
    db_label.thumbnail_path = f"/api/v1/labels/{label_id}/thumbnail"
    try:
        db.add(db_label)
        await db.commit()
        await db.refresh(db_label)
        return LabelResponse.model_validate(db_label)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update label thumbnail: {e!s}",
        ) from e


@router.get(
    "/labels/{label_id}/thumbnail",
)
async def get_label_thumbnail(
    label_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Return the thumbnail image file for a label, if present."""
    # Fetch label for project and to verify existence
    result = await db.execute(select(Label).where(Label.id == label_id))
    db_label = result.scalar_one_or_none()
    if db_label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label with ID {label_id} not found",
        )

    root = Path(settings.PROJECTS_ROOT_DIR)
    project_dir = root / str(db_label.project_id)
    thumbs_dir = project_dir / "label_thumbs"

    # Try known extensions
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = thumbs_dir / f"{label_id}{ext}"
        if candidate.exists():
            return FileResponse(candidate)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Thumbnail not found for this label",
    )
