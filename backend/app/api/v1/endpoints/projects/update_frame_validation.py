"""Update validation status for a frame."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ImageListResponse, ImageResponse, ImageValidationUpdate
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


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
        images_result = await db.execute(
            select(Image)
            .where(Image.project_id == project_id)
            .order_by(Image.frame_number)
        )
        images = images_result.scalars().all()
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

        if update.validation == "passed":
            start_index = last_manual_index if last_manual_index is not None else current_index
            end_index = current_index
        else:
            start_index = current_index
            if last_manual_index is not None:
                max_end_frame = (
                    images[last_manual_index].frame_number
                    + settings.MAX_PROPAGATION_LENGTH
                )
            else:
                max_end_frame = images[current_index].frame_number + settings.MAX_PROPAGATION_LENGTH

            next_manual_frame = (
                images[next_manual_index].frame_number
                if next_manual_index is not None
                else max_end_frame
            )
            end_frame = min(next_manual_frame, max_end_frame)
            end_index = current_index
            for idx in range(current_index, len(images)):
                if images[idx].frame_number <= end_frame:
                    end_index = idx
                else:
                    break

        for idx in range(start_index, end_index + 1):
            if images[idx].manually_labeled:
                continue
            images[idx].validation = update.validation
            db.add(images[idx])

        await db.commit()
        for idx in range(start_index, end_index + 1):
            await db.refresh(images[idx])

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
