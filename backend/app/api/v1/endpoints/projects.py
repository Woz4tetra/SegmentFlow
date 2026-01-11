"""Projects endpoint for CRUD operations."""

import io
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    VideoUploadCompleteResponse,
    VideoUploadProgressResponse,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.video_upload import VideoUploadService
from app.core.video_frames import read_frame_at_time, convert_range_to_jpegs, get_video_info
from app.models.project import Project, ProjectStage

logger = get_logger(__name__)
router = APIRouter()

# Global video upload service instance
_upload_service = VideoUploadService()


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project.

    Creates a new project with the provided name and settings.
    The project starts in the UPLOAD stage.

    Args:
        project_in: Project creation request
        db: Database session dependency

    Returns:
        ProjectResponse: The created project

    Raises:
        HTTPException: If project creation fails
    """
    try:
        db_project = Project(
            name=project_in.name,
            active=project_in.active,
        )
        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        return ProjectResponse.model_validate(db_project)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create project: {e!s}",
        ) from e


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """List all projects.

    Retrieves all projects sorted by most recently updated first.

    Args:
        db: Database session dependency

    Returns:
        ProjectListResponse: List of projects and total count

    Raises:
        HTTPException: If database query fails
    """
    try:
        # Query all projects ordered by updated_at descending
        result = await db.execute(
            select(Project).order_by(Project.updated_at.desc()),
        )
        projects = result.scalars().all()

        return ProjectListResponse(
            projects=[ProjectResponse.model_validate(p) for p in projects],
            total=len(projects),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {e!s}",
        ) from e


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get a project by ID.

    Retrieves a specific project with all its details.

    Args:
        project_id: ID of the project to retrieve
        db: Database session dependency

    Returns:
        ProjectResponse: The requested project

    Raises:
        HTTPException: If project not found or query fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {e!s}",
        ) from e


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update a project.

    Updates one or more fields of an existing project.
    Only provided fields are updated.

    Args:
        project_id: ID of the project to update
        project_in: Project update request with fields to update
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If project not found or update fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Update only provided fields
        update_data = project_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_project, field, value)

        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update project: {e!s}",
        ) from e


# ===== Video Upload Endpoints =====


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
        _upload_service.start_upload(
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
        _upload_service.save_chunk(
            str(project_id),
            chunk_number,
            chunk_bytes,
        )

        # Get progress
        progress = _upload_service.get_progress(str(project_id))

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


@router.post("/projects/{project_id}/upload/complete")
async def complete_video_upload(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> VideoUploadCompleteResponse:
    """Finalize a video upload.

    Combines all uploaded chunks, verifies file integrity via file hash,
    and updates the project with the video path. Should be called after all
    chunks have been uploaded.

    Args:
        project_id: ID of the project
        db: Database session dependency

    Returns:
        VideoUploadCompleteResponse: Confirmation with video path and file size

    Raises:
        HTTPException: If project not found, upload not in progress, or finalization fails
    """
    try:
        logger.info(f"Received complete upload request for project {project_id}")

        # Verify project exists
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Determine output path for video
        projects_root = Path(settings.PROJECTS_ROOT_DIR)
        project_dir = projects_root / str(project_id)
        videos_dir = project_dir / "videos"
        # Determine extension from original filename if available
        session = _upload_service._sessions.get(str(project_id))  # scoped use
        default_ext = ".mp4"
        ext = default_ext
        if session and session.original_name:
            ext_candidate = Path(session.original_name).suffix.lower()
            if ext_candidate in {".mp4", ".mov", ".avi"}:
                ext = ext_candidate
        output_path = videos_dir / f"original{ext}"

        logger.info(f"Finalizing upload to {output_path}")

        # Finalize upload (combine chunks, verify hash, cleanup temp files)
        _upload_service.finalize_upload(str(project_id), output_path)

        # Update project with video path and advance stage to TRIM
        db_project.video_path = str(output_path)
        db_project.stage = ProjectStage.TRIM.value
        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)

        file_size = output_path.stat().st_size

        logger.info(
            f"Completed video upload for project {project_id}: "
            f"{file_size} bytes saved to {output_path}"
        )

        return VideoUploadCompleteResponse(
            project_id=project_id,
            video_path=str(output_path),
            file_size=file_size,
            message="Video upload completed successfully",
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except RuntimeError as e:
        logger.error(f"Upload verification failed for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Upload verification failed: {e!s}",
        ) from e
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to complete upload for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize upload",
        ) from e


@router.get("/projects/{project_id}/video")
async def get_project_video(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stream the uploaded video file for a project.

    Returns the original uploaded video for preview/trim UI.

    Args:
        project_id: ID of the project
        db: Database session dependency

    Returns:
        FileResponse: The video file response

    Raises:
        HTTPException: If project not found or video missing
    """
    # Fetch and validate project
    result = await db.execute(select(Project).where(Project.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not db_project.video_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No video for project")

    video_path = Path(db_project.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file missing")

    # Media type
    ext = video_path.suffix.lower()
    media_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo"}
    media_type = media_map.get(ext, "application/octet-stream")

    # Byte-range support
    range_header = request.headers.get("range")
    file_size = video_path.stat().st_size
    if range_header:
        try:
            bytes_range = range_header.strip().lower().split("=")[1]
            parts = bytes_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            start = max(0, start)
            end = min(end, file_size - 1)
            chunk_size = (end - start) + 1

            def iter_file(path: Path, offset: int, length: int):
                with open(path, "rb") as f:
                    f.seek(offset)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Content-Type": media_type,
            }
            return StreamingResponse(
                iter_file(video_path, start, chunk_size),
                status_code=206,
                headers=headers,
                media_type=media_type,
            )
        except Exception:
            # Fallback to full file on parse errors
            pass

    return FileResponse(str(video_path), media_type=media_type)


@router.post("/projects/{project_id}/trim", response_model=ProjectResponse)
async def set_trim_range(
    project_id: UUID,
    trim_start: int,
    trim_end: int,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update the project's trim range with basic validation.

    Args:
        project_id: ID of the project
        trim_start: Start position (units currently seconds or frames TBD)
        trim_end: End position (must be greater than start)
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If project not found or validation fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        if trim_start < 0 or trim_end <= trim_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid trim range: ensure start >= 0 and end > start",
            )

        db_project.trim_start = trim_start
        db_project.trim_end = trim_end
        # Keep stage as TRIM; conversion/manual labeling will advance later
        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to set trim for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set trim range",
        ) from e


@router.get("/projects/{project_id}/preview_frame")
async def preview_frame(
    project_id: UUID,
    time_sec: float,
    db: AsyncSession = Depends(get_db),
):
    """Return a single JPEG frame at the given time for preview purposes."""
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not db_project.video_path:
            raise HTTPException(status_code=404, detail="No video for project")
        jpeg = read_frame_at_time(Path(db_project.video_path), float(time_sec))
        return StreamingResponse(io.BytesIO(jpeg), media_type="image/jpeg")
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"OpenCV not available: {e}") from e
    except Exception as e:
        logger.error(f"Failed to generate preview for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate preview") from e


@router.post("/projects/{project_id}/convert_images")
async def convert_images(
    project_id: UUID,
    trim_start: float,
    trim_end: float,
    processes: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Convert frames within selected range to JPEG and save under project folder."""
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not db_project.video_path:
            raise HTTPException(status_code=404, detail="No video for project")

        projects_root = Path(settings.PROJECTS_ROOT_DIR)
        out_dir = projects_root / str(project_id) / "output"
        out_dir.mkdir(parents=True, exist_ok=True)

        summary = convert_range_to_jpegs(
            Path(db_project.video_path), float(trim_start), float(trim_end), out_dir, processes
        )
        return {
            "project_id": str(project_id),
            "output_dir": str(out_dir),
            "total": summary["total"],
            "saved": summary["saved"],
            "message": "Conversion completed",
        }
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"OpenCV not available: {e}") from e
    except Exception as e:
        logger.error(f"Failed to convert images for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to convert images") from e


@router.get("/projects/{project_id}/video_info")
async def video_info(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return basic video metadata: fps, frame_count, width, height, duration."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not db_project.video_path:
        raise HTTPException(status_code=404, detail="No video for project")
    info = get_video_info(Path(db_project.video_path))
    duration = (info.frame_count / info.fps) if info.fps > 0 else 0.0
    return {
        "fps": info.fps,
        "frame_count": info.frame_count,
        "width": info.width,
        "height": info.height,
        "duration": duration,
    }


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
        progress = _upload_service.get_progress(str(project_id))

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
        _upload_service.cancel_upload(str(project_id))

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
