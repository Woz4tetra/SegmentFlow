from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import MaskResponse
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.image import Image
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.get(
    "/projects/{project_id}/frames/{frame_number}/masks",
    response_model=list[MaskResponse],
)
async def get_masks(
    project_id: UUID,
    frame_number: int,
    label_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[MaskResponse]:
    """Get masks for a specific frame.

    Args:
        project_id: ID of the project
        frame_number: Frame number (0-indexed)
        label_id: Optional label ID to filter by
        db: Database session dependency

    Returns:
        list[MaskResponse]: List of masks

    Raises:
        HTTPException: If project or image not found
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

        # Query masks
        query = select(Mask).where(Mask.image_id == image.id)
        if label_id:
            query = query.where(Mask.label_id == label_id)

        masks_result = await db.execute(query)
        masks = masks_result.scalars().all()

        return [MaskResponse.model_validate(m) for m in masks]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get masks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get masks: {e!s}",
        ) from e
