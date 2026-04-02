"""Label endpoints for CRUD operations."""

from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import LabelCreate, LabelResponse, LabelUpdate
from app.core.config import settings
from app.core.database import get_db
from app.models.label import Label

router = APIRouter()
THUMBNAIL_SIZE = 128


def _resize_thumbnail_to_square(image: np.ndarray, target_size: int = THUMBNAIL_SIZE) -> np.ndarray:
    height, width = image.shape[:2]
    side = min(height, width)
    top = max(0, (height - side) // 2)
    left = max(0, (width - side) // 2)
    cropped = image[top : top + side, left : left + side]
    if cropped.shape[0] == target_size and cropped.shape[1] == target_size:
        return cropped
    return cv2.resize(cropped, (target_size, target_size), interpolation=cv2.INTER_AREA)


@router.get(
    "/labels",
    response_model=list[LabelResponse],
)
async def list_labels(
    db: AsyncSession = Depends(get_db),
) -> list[LabelResponse]:
    """List all global labels."""
    label_result = await db.execute(select(Label).order_by(Label.created_at))
    labels = label_result.scalars().all()
    return [LabelResponse.model_validate(label) for label in labels]


@router.post(
    "/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_label(
    label_in: LabelCreate,
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Create a new global label."""
    try:
        db_label = Label(
            name=label_in.name,
            color_hex=label_in.color_hex,
            thumbnail_path=label_in.thumbnail_path,
            always_include=label_in.always_include,
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
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    """Upload and set a thumbnail image for a global label.

    Files are stored under a global directory: `{PROJECTS_ROOT_DIR}/label_thumbs/`.
    """
    # Fetch label
    result = await db.execute(select(Label).where(Label.id == label_id))
    db_label = result.scalar_one_or_none()
    if db_label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label with ID {label_id} not found",
        )

    # Prepare destination directory and file path
    root = Path(settings.PROJECTS_ROOT_DIR)
    thumbs_dir = root / "label_thumbs"
    try:
        thumbs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare thumbnail directory: {e!s}",
        ) from e

    # Normalize all uploaded thumbnails to 128x128 JPG.
    dest_path = thumbs_dir / f"{label_id}.jpg"

    try:
        contents = await file.read()
        np_data = np.frombuffer(contents, dtype=np.uint8)
        decoded = cv2.imdecode(np_data, cv2.IMREAD_UNCHANGED)
        if decoded is None:
            raise ValueError("Unsupported or invalid image data")
        resized = _resize_thumbnail_to_square(decoded)
        if resized.ndim == 3 and resized.shape[2] == 4:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2BGR)
        if resized.ndim == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
        ok = cv2.imwrite(str(dest_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError("Failed to encode resized thumbnail")
        # Remove legacy files so the fetch endpoint always serves normalized JPG.
        for ext in (".png", ".jpeg"):
            legacy_path = thumbs_dir / f"{label_id}{ext}"
            if legacy_path.exists():
                legacy_path.unlink()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save thumbnail: {e!s}",
        ) from e

    # Update label thumbnail_path to served route
    base_url = str(request.base_url).rstrip("/") if request else ""
    db_label.thumbnail_path = f"{base_url}{settings.API_V1_STR}/labels/{label_id}/thumbnail"
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
    """Return the thumbnail image file for a global label, if present."""
    result = await db.execute(select(Label).where(Label.id == label_id))
    db_label = result.scalar_one_or_none()
    if db_label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label with ID {label_id} not found",
        )

    root = Path(settings.PROJECTS_ROOT_DIR)
    thumbs_dir = root / "label_thumbs"
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = thumbs_dir / f"{label_id}{ext}"
        if candidate.exists():
            return FileResponse(candidate)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Thumbnail not found for this label",
    )
