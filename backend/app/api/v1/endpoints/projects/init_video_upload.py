from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.project import Project

from .shared_objects import router, upload_service

logger = get_logger(__name__)


@router.post("/projects/{project_id}/upload/init")
async def init_video_upload(
    project_id: UUID,
    total_chunks: int,
    total_size: int,
    file_hash: str,
    original_name: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Initialize a video upload session.

    Sets up the upload session for a project, validating that the project exists
    and that the file meets size requirements. Clients should call this before
    uploading chunks.

    Args:
        project_id: ID of the project to upload video to
        total_chunks: Total number of chunks that will be uploaded
        total_size: Total size of the video file in bytes
        file_hash: file hash of the complete file for integrity verification
        db: Database session dependency

    Returns:
        dict: Confirmation with project_id and message

    Raises:
        HTTPException: If project not found, file too large, or upload already in progress
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

        # Initialize upload session
        upload_service.start_upload(
            str(project_id),
            total_chunks,
            total_size,
            file_hash,
            original_name,
        )

        logger.info(
            f"Initialized video upload for project {project_id}: "
            f"{total_size} bytes in {total_chunks} chunks"
        )
        return {
            "project_id": str(project_id),
            "message": "Upload session initialized",
            "total_chunks": total_chunks,
            "total_size": total_size,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to initialize upload for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize upload",
        ) from e
