from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import VideoUploadProgressResponse
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.project import Project

from .shared_objects import router, upload_service

logger = get_logger(__name__)


@router.get("/projects/{project_id}/upload/progress")
async def get_upload_progress(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> VideoUploadProgressResponse:
    """Get current upload progress for a project.

    Returns progress information for an in-progress video upload.

    Args:
        project_id: ID of the project
        db: Database session dependency

    Returns:
        VideoUploadProgressResponse: Current upload progress

    Raises:
        HTTPException: If project not found or no upload in progress
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

        # Get progress
        progress = upload_service.get_progress(str(project_id))

        return VideoUploadProgressResponse(
            project_id=project_id,
            total_size=progress.get("total_size", 0),
            uploaded_size=progress["uploaded_size"],
            progress_percent=progress["progress_percent"],
            chunks_received=progress["chunks_received"],
            total_chunks=progress["total_chunks"],
            status=progress["status"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to get upload progress for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get progress",
        ) from e
