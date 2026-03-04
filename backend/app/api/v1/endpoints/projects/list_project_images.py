from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ImageListResponse, ImageResponse
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.get("/projects/{project_id}/images", response_model=ImageListResponse)
async def list_project_images(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ImageListResponse:
    """List all images/frames for a project.

    Returns all images for a project with their status information.
    Used by the manual labeling UI to track frame status.

    Args:
        project_id: ID of the project
        db: Database session dependency

    Returns:
        ImageListResponse: List of all images with their metadata

    Raises:
        HTTPException: If project not found or database query fails
    """
    try:
        # Verify project exists
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Query images for this project within trim range (if set)
        bounds = get_trim_frame_bounds(db_project)
        query = select(Image).where(Image.project_id == project_id)
        if bounds:
            start_frame, end_frame = bounds
            query = query.where(
                Image.frame_number >= start_frame,
                Image.frame_number <= end_frame,
            )
        images_result = await db.execute(query.order_by(Image.frame_number))
        images = images_result.scalars().all()

        return ImageListResponse(
            images=[ImageResponse.model_validate(img) for img in images],
            total=len(images),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list images for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list images: {e!s}",
        ) from e
