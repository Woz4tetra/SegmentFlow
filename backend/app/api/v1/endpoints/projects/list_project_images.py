from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ImageListResponse, ImageResponse
from app.core.database import get_db
from app.core.logging import get_logger
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

        # Query all images for this project, ordered by frame number
        images_result = await db.execute(
            select(Image).where(Image.project_id == project_id).order_by(Image.frame_number)
        )
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
