from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import MaskResponse, SaveMaskRequest
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import is_frame_in_trim
from app.models.image import Image
from app.models.label import Label
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.post(
    "/projects/{project_id}/frames/{frame_number}/masks",
    response_model=MaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_mask(
    project_id: UUID,
    frame_number: int,
    request: SaveMaskRequest,
    db: AsyncSession = Depends(get_db),
) -> MaskResponse:
    """Save a mask for a specific frame.

    Args:
        project_id: ID of the project
        frame_number: Frame number (0-indexed)
        request: Mask data to save
        db: Database session dependency

    Returns:
        MaskResponse: Saved mask

    Raises:
        HTTPException: If project, image, or label not found
    """
    try:
        # Verify project exists
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        if not is_frame_in_trim(project, frame_number):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frame {frame_number} outside trim range",
            )

        # Get image for this frame
        image_result = await db.execute(
            select(Image).where(
                Image.project_id == project_id,
                Image.frame_number == frame_number,
            )
        )
        image = image_result.scalar_one_or_none()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image not found for frame {frame_number}",
            )

        # Verify label exists
        label_result = await db.execute(select(Label).where(Label.id == request.label_id))
        label = label_result.scalar_one_or_none()
        if not label:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Label with ID {request.label_id} not found",
            )

        # Check if mask already exists for this image and label
        existing_mask_result = await db.execute(
            select(Mask).where(
                Mask.image_id == image.id,
                Mask.label_id == request.label_id,
            )
        )
        existing_mask = existing_mask_result.scalar_one_or_none()

        if existing_mask:
            # Update existing mask
            existing_mask.contour_polygon = request.mask.contour_polygon
            existing_mask.area = request.mask.area
            db.add(existing_mask)
            mask = existing_mask
        else:
            # Create new mask
            db_mask = Mask(
                image_id=image.id,
                label_id=request.label_id,
                contour_polygon=request.mask.contour_polygon,
                area=request.mask.area,
            )
            db.add(db_mask)
            mask = db_mask

        # Mark image as manually labeled
        image.manually_labeled = True
        db.add(image)

        await db.commit()
        await db.refresh(mask)

        logger.info(
            f"Successfully saved mask for project {project_id}, "
            f"frame {frame_number}, label {request.label_id} with area {request.mask.area}"
        )

        return MaskResponse.model_validate(mask)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save mask: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save mask: {e!s}",
        ) from e
