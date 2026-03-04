"""Clear labeled points and masks from a frame.

Provides endpoints to clear labeled points and masks for:
- A specific label on a frame
- All labels on a frame
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import is_frame_in_trim
from app.models.image import Image
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.delete(
    "/projects/{project_id}/frames/{frame_number}/labels",
    summary="Clear labels from a frame",
    description="Clear labeled points and masks from a frame. "
    "Optionally specify a label_id to clear only that label.",
)
async def clear_frame_labels(
    project_id: UUID,
    frame_number: int,
    label_id: UUID | None = Query(None, description="Label ID to clear (omit to clear all)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clear labeled points and masks from a frame.

    Args:
        project_id: UUID of the project
        frame_number: Frame number (0-indexed)
        label_id: Optional label ID to clear only that label's data
        db: Database session

    Returns:
        Dict with counts of deleted points and masks
    """
    # Verify project exists
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    if not is_frame_in_trim(project, frame_number):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame {frame_number} outside trim range",
        )

    # Find the image
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

    # Build delete queries
    if label_id:
        # Delete only for specific label
        points_query = delete(LabeledPoint).where(
            LabeledPoint.image_id == image.id,
            LabeledPoint.label_id == label_id,
        )
        masks_query = delete(Mask).where(
            Mask.image_id == image.id,
            Mask.label_id == label_id,
        )
    else:
        # Delete all labels for this frame
        points_query = delete(LabeledPoint).where(LabeledPoint.image_id == image.id)
        masks_query = delete(Mask).where(Mask.image_id == image.id)

    # Execute deletes
    points_result = await db.execute(points_query)
    masks_result = await db.execute(masks_query)

    points_deleted = points_result.rowcount
    masks_deleted = masks_result.rowcount

    # Check if there are any remaining labeled points for this image
    remaining_points = await db.execute(
        select(LabeledPoint).where(LabeledPoint.image_id == image.id).limit(1)
    )
    has_remaining_points = remaining_points.scalar_one_or_none() is not None

    # Update manually_labeled status
    if not has_remaining_points:
        image.manually_labeled = False

    await db.commit()

    logger.info(
        f"Cleared frame {frame_number} labels: "
        f"{points_deleted} points, {masks_deleted} masks deleted"
        f"{f' for label {label_id}' if label_id else ' (all labels)'}"
    )

    return {
        "success": True,
        "points_deleted": points_deleted,
        "masks_deleted": masks_deleted,
        "label_id": str(label_id) if label_id else None,
        "frame_number": frame_number,
        "manually_labeled": image.manually_labeled,
    }
