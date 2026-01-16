from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.project import Project

from .shared_objects import router, upload_service

logger = get_logger(__name__)


@router.delete("/projects/{project_id}/upload")
async def cancel_video_upload(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel an in-progress video upload.

    Cancels the upload session and cleans up temporary files.

    Args:
        project_id: ID of the project
        db: Database session dependency

    Returns:
        dict: Confirmation message

    Raises:
        HTTPException: If project not found
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

        # Cancel upload and cleanup
        upload_service.cancel_upload(str(project_id))

        logger.info(f"Cancelled video upload for project {project_id}")
        return {
            "project_id": str(project_id),
            "message": "Upload cancelled and temporary files cleaned up",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel upload for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel upload",
        ) from e
