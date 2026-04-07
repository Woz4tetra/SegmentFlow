"""Update validation status for a frame."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    ImageListResponse,
    ImageResponse,
    ImageValidationRangeResponse,
    ImageValidationUpdate,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


async def _compute_and_apply_validation_range_compact(
    project_id: UUID,
    frame_number: int,
    validation_value: str,
    db: AsyncSession,
) -> tuple[list[int], int, int]:
    rows_result = await db.execute(
        select(Image.id, Image.frame_number, Image.manually_labeled)
        .where(Image.project_id == project_id)
        .order_by(Image.frame_number)
    )
    rows = list(rows_result.all())
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    bounds = get_trim_frame_bounds(project) if project else None
    if bounds:
        start_frame, end_frame = bounds
        rows = [row for row in rows if start_frame <= row.frame_number <= end_frame]
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame {frame_number} not found for project {project_id}",
        )

    current_index = next(
        (idx for idx, row in enumerate(rows) if row.frame_number == frame_number),
        None,
    )
    if current_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame {frame_number} not found for project {project_id}",
        )

    last_manual_index = None
    next_manual_index = None
    for idx in range(current_index, -1, -1):
        if rows[idx].manually_labeled:
            last_manual_index = idx
            break
    for idx in range(current_index + 1, len(rows)):
        if rows[idx].manually_labeled:
            next_manual_index = idx
            break

    if validation_value == "passed":
        start_index = last_manual_index if last_manual_index is not None else current_index
        end_index = current_index
    else:
        start_index = current_index
        next_manual_frame = (
            rows[next_manual_index].frame_number
            if next_manual_index is not None
            else rows[-1].frame_number
        )
        end_frame = next_manual_frame
        end_index = current_index
        for idx in range(current_index, len(rows)):
            if rows[idx].frame_number <= end_frame:
                end_index = idx
            else:
                break

    range_start_frame = rows[start_index].frame_number
    range_end_frame = rows[end_index].frame_number
    updated_ids: list[UUID] = []
    updated_frame_numbers: list[int] = []
    for idx in range(start_index, end_index + 1):
        if rows[idx].manually_labeled:
            continue
        updated_ids.append(rows[idx].id)
        updated_frame_numbers.append(rows[idx].frame_number)

    if updated_ids:
        await db.execute(
            update(Image)
            .where(Image.id.in_(updated_ids))
            .values(validation=validation_value)
        )
    await db.commit()
    return updated_frame_numbers, range_start_frame, range_end_frame


async def _compute_and_apply_validation_range(
    project_id: UUID,
    frame_number: int,
    validation_value: str,
    db: AsyncSession,
) -> tuple[list[Image], list[int], int, int]:
    images_result = await db.execute(
        select(Image)
        .where(Image.project_id == project_id)
        .order_by(Image.frame_number)
    )
    images = list(images_result.scalars().all())
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    bounds = get_trim_frame_bounds(project) if project else None
    if bounds:
        start_frame, end_frame = bounds
        images = [
            img
            for img in images
            if start_frame <= img.frame_number <= end_frame
        ]
    if not images:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame {frame_number} not found for project {project_id}",
        )

    current_index = next(
        (idx for idx, img in enumerate(images) if img.frame_number == frame_number),
        None,
    )
    if current_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame {frame_number} not found for project {project_id}",
        )

    last_manual_index = None
    next_manual_index = None
    for idx in range(current_index, -1, -1):
        if images[idx].manually_labeled:
            last_manual_index = idx
            break
    for idx in range(current_index + 1, len(images)):
        if images[idx].manually_labeled:
            next_manual_index = idx
            break

    if validation_value == "passed":
        start_index = last_manual_index if last_manual_index is not None else current_index
        end_index = current_index
    else:
        start_index = current_index
        next_manual_frame = (
            images[next_manual_index].frame_number
            if next_manual_index is not None
            else images[-1].frame_number
        )
        end_frame = next_manual_frame
        end_index = current_index
        for idx in range(current_index, len(images)):
            if images[idx].frame_number <= end_frame:
                end_index = idx
            else:
                break

    range_start_frame = images[start_index].frame_number
    range_end_frame = images[end_index].frame_number
    updated_ids: list[UUID] = []
    updated_frame_numbers: list[int] = []
    for idx in range(start_index, end_index + 1):
        if images[idx].manually_labeled:
            continue
        updated_ids.append(images[idx].id)
        updated_frame_numbers.append(images[idx].frame_number)

    if updated_ids:
        await db.execute(
            update(Image)
            .where(Image.id.in_(updated_ids))
            .values(validation=validation_value)
        )
    await db.commit()

    updated_set = set(updated_frame_numbers)
    for img in images:
        if img.frame_number in updated_set:
            img.validation = validation_value

    return images, updated_frame_numbers, range_start_frame, range_end_frame


@router.patch(
    "/projects/{project_id}/frames/{frame_number}/validation",
    response_model=ImageListResponse,
)
async def update_frame_validation(
    project_id: UUID,
    frame_number: int,
    update: ImageValidationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ImageListResponse:
    """Update validation status for a specific frame.

    Args:
        project_id: Project ID
        frame_number: Frame number to update
        update: Validation update payload
        db: Database session dependency

    Returns:
        ImageResponse: Updated image

    Raises:
        HTTPException: If image not found or update fails
    """
    try:
        images, _, _, _ = await _compute_and_apply_validation_range(
            project_id=project_id,
            frame_number=frame_number,
            validation_value=update.validation,
            db=db,
        )

        return ImageListResponse(
            images=[ImageResponse.model_validate(img) for img in images],
            total=len(images),
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "Failed to update validation for project %s frame %s: %s",
            project_id,
            frame_number,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update validation status",
        ) from e


@router.patch(
    "/projects/{project_id}/frames/{frame_number}/validation/range",
    response_model=ImageValidationRangeResponse,
)
async def update_frame_validation_range(
    project_id: UUID,
    frame_number: int,
    update: ImageValidationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ImageValidationRangeResponse:
    """Update validation status over computed range and return compact result."""
    try:
        updated_frame_numbers, start_frame, end_frame = await _compute_and_apply_validation_range_compact(
            project_id=project_id,
            frame_number=frame_number,
            validation_value=update.validation,
            db=db,
        )
        return ImageValidationRangeResponse(
            validation=update.validation,
            updated_frame_numbers=updated_frame_numbers,
            updated_count=len(updated_frame_numbers),
            start_frame=start_frame,
            end_frame=end_frame,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "Failed to update validation range for project %s frame %s: %s",
            project_id,
            frame_number,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update validation status",
        ) from e
