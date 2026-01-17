from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import is_frame_in_trim
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.get("/projects/{project_id}/frames/{frame_number}")
async def get_frame_image(
    project_id: UUID,
    frame_number: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Get the inference-resolution image for a specific frame.

    Serves the JPEG file for displaying in the manual labeling UI canvas.

    Args:
        project_id: ID of the project
        frame_number: Frame number (0-indexed)
        db: Database session dependency

    Returns:
        FileResponse: JPEG image file

    Raises:
        HTTPException: If project, image, or file not found
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

        if not is_frame_in_trim(db_project, frame_number):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frame {frame_number} outside trim range",
            )

        # Construct path to inference image
        # Images are stored as frame_NNNNNN.jpg where NNNNNN is zero-padded frame number
        frame_path = (
            Path(settings.PROJECTS_ROOT_DIR)
            / str(project_id)
            / "inference"
            / f"frame_{frame_number:06d}.jpg"
        )

        if not frame_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Frame {frame_number} not found or not yet generated",
            )

        return FileResponse(
            str(frame_path),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get frame {frame_number} for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get frame image",
        ) from e
