from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import LabeledPointResponse, SaveLabeledPointsRequest
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.image import Image
from app.models.label import Label
from app.models.labeled_point import LabeledPoint
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.post(
    "/projects/{project_id}/frames/{frame_number}/points",
    response_model=list[LabeledPointResponse],
    status_code=status.HTTP_201_CREATED,
)
async def save_labeled_points(
    project_id: UUID,
    frame_number: int,
    request: SaveLabeledPointsRequest,
    db: AsyncSession = Depends(get_db),
) -> list[LabeledPointResponse]:
    """Save labeled points for a specific frame.

    Args:
        project_id: ID of the project
        frame_number: Frame number (0-indexed)
        request: Points to save
        db: Database session dependency

    Returns:
        list[LabeledPointResponse]: List of saved points

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

        # Delete existing points for this image and label
        existing_points_result = await db.execute(
            select(LabeledPoint).where(
                LabeledPoint.image_id == image.id,
                LabeledPoint.label_id == request.label_id,
            )
        )
        existing_points = existing_points_result.scalars().all()
        for point in existing_points:
            await db.delete(point)

        # Create new points
        saved_points = []
        for point_data in request.points:
            db_point = LabeledPoint(
                image_id=image.id,
                label_id=request.label_id,
                x=point_data.x,
                y=point_data.y,
                include=point_data.include,
            )
            db.add(db_point)
            saved_points.append(db_point)

        # Mark image as manually labeled
        image.manually_labeled = True
        db.add(image)

        await db.commit()

        # Refresh points to get IDs
        for point in saved_points:
            await db.refresh(point)

        return [LabeledPointResponse.model_validate(p) for p in saved_points]

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save labeled points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save labeled points: {e!s}",
        ) from e
