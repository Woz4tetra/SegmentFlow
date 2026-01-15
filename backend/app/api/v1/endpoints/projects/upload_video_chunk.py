from uuid import UUID

from fastapi import Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import VideoUploadProgressResponse
from app.core.database import get_db
from app.core.logging import get_logger

from .shared_objects import router, upload_service

logger = get_logger(__name__)


@router.post("/projects/{project_id}/upload/chunk")
async def upload_video_chunk(
    project_id: UUID,
    chunk_number: int,
    chunk_data: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> VideoUploadProgressResponse:
    """Upload a single chunk of a video file.

    Accepts one chunk of a chunked video upload. The upload session must be
    initialized first via /upload/init. Returns current progress information.

    Args:
        project_id: ID of the project
        chunk_number: Sequential chunk number (0-indexed)
        chunk_data: Binary chunk data from the file
        db: Database session dependency

    Returns:
        VideoUploadProgressResponse: Current upload progress

    Raises:
        HTTPException: If upload session not found, chunk invalid, or save fails
    """
    try:
        # Read chunk data
        chunk_bytes = await chunk_data.read()
        logger.info(
            f"Received chunk upload request: project={project_id}, "
            f"chunk={chunk_number}, size={len(chunk_bytes)} bytes"
        )

        # Save chunk to upload service
        upload_service.save_chunk(
            str(project_id),
            chunk_number,
            chunk_bytes,
        )

        # Get progress
        progress = upload_service.get_progress(str(project_id))

        logger.info(
            f"Chunk {chunk_number} processed for project {project_id}: "
            f"{progress['chunks_received']}/{progress['total_chunks']} chunks received, "
            f"{progress['progress_percent']:.1f}% complete"
        )

        return VideoUploadProgressResponse(
            project_id=project_id,
            total_size=progress["uploaded_size"],  # Will update on finalize
            uploaded_size=progress["uploaded_size"],
            progress_percent=progress["progress_percent"],
            chunks_received=progress["chunks_received"],
            total_chunks=progress["total_chunks"],
            status=progress["status"],
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to upload chunk for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save chunk",
        ) from e
