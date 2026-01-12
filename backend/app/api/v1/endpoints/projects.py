"""Projects endpoint for CRUD operations."""

import threading
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
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
from app.core.video_frames import convert_video_to_jpegs, generate_thumbnail, get_video_info
from app.core.video_upload import VideoUploadService
from app.models.project import Project, ProjectStage

logger = get_logger(__name__)
router = APIRouter()

# Global video upload service instance
_upload_service = VideoUploadService()

# In-memory conversion progress tracker: {project_id: {"saved": int, "total": int, "error": bool}}
_conversion_progress: dict[str, dict[str, int | bool]] = {}


def convert_video_task(
    project_id: UUID,
    video_path: Path,
    project_dir: Path,
    output_width: int,
    inference_width: int,
) -> None:
    project_id_str = str(project_id)
    logger.info(f"[BG] Starting conversion for project {project_id}")
    _conversion_progress[project_id_str] = {"saved": 0, "total": 0, "error": False}
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    inference_dir = project_dir / "inference"
    inference_dir.mkdir(parents=True, exist_ok=True)

    def progress_cb(saved: int, total: int) -> None:
        _conversion_progress[project_id_str]["saved"] = saved
        _conversion_progress[project_id_str]["total"] = total
        logger.debug(f"[BG] Conversion progress {project_id}: {saved}/{total}")

    did_error = convert_video_to_jpegs(
        video_path,
        output_dir,
        inference_dir,
        output_width,
        inference_width,
        progress_callback=progress_cb,
    )
    _conversion_progress[project_id_str]["error"] = did_error
    logger.info(
        f"[BG] JPEG conversion {'failed' if did_error else 'succeeded'} for project {project_id}"
    )
    if did_error:
        return

    # Generate thumbnail from first available frame in output directory
    thumbnail_path = project_dir / "thumbnail.jpg"
    try:
        # Find the first frame file (sorted by frame number)
        frame_files = list(output_dir.glob("frame_*.jpg"))
        if frame_files:
            # Sort by extracting the numeric part from filename
            frame_files.sort(key=lambda p: int(p.stem.split("_")[1]))
            generate_thumbnail(frame_files[0], thumbnail_path, max_width=320, quality=75)
            logger.info(f"[BG] Thumbnail generated for project {project_id}")
        else:
            logger.warning(f"[BG] No frames found to generate thumbnail for project {project_id}")
    except Exception as thumb_err:
        logger.error(
            f"[BG] Failed to generate thumbnail for project {project_id}: {thumb_err}",
            exc_info=thumb_err,
        )
        _conversion_progress[project_id_str]["error"] = True


def _start_conversion_background(
    project_id: UUID,
    video_path: Path,
    project_dir: Path,
    output_width: int,
    inference_width: int,
) -> None:
    """Start video-to-JPEG conversion in background thread.

    Args:
        project_id: Project UUID
        video_path: Path to video file
        project_dir: Project directory
        output_width: width of the output image
        inference_width: width of the inference image
    """

    # Start conversion in background thread
    thread = threading.Thread(
        target=convert_video_task,
        args=(project_id, video_path, project_dir, output_width, inference_width),
        daemon=True,
    )
    thread.start()
    logger.info(f"Background conversion thread started for project {project_id}")


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


@router.post("/projects/{project_id}/mark_stage_visited", response_model=ProjectResponse)
async def mark_stage_visited(
    project_id: UUID,
    stage: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Mark a stage as visited for a project.

    Updates the appropriate stage_visited flag when a user visits a stage.
    This is used to control stage navigation permissions.

    Args:
        project_id: ID of the project to update
        stage: Stage name to mark as visited (e.g., "upload", "trim", "manual_labeling")
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If project not found or invalid stage name
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Map stage name to visited field
        stage_field_map = {
            "upload": "upload_visited",
            "trim": "trim_visited",
            "manual_labeling": "manual_labeling_visited",
            "propagation": "propagation_visited",
            "validation": "validation_visited",
            "export": "export_visited",
        }

        if stage not in stage_field_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {stage}",
            )

        # Mark the stage as visited
        field_name = stage_field_map[stage]
        setattr(db_project, field_name, True)

        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        logger.info(f"Marked stage '{stage}' as visited for project {project_id}")
        return ProjectResponse.model_validate(db_project)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark stage as visited: {e!s}",
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
        session = _upload_service.get_session(str(project_id))  # scoped use
        default_ext = ".mp4"
        ext = default_ext
        if session and session.original_name:
            ext_candidate = Path(session.original_name).suffix.lower()
            if ext_candidate in {".mp4", ".mov", ".avi"}:
                ext = ext_candidate
        output_path = videos_dir / f"original{ext}"

        output_width = settings.OUTPUT_WIDTH
        inference_width = settings.INFERENCE_WIDTH

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
        # Start background conversion for full video JPEG extraction
        logger.info(f"Starting background conversion for project {project_id}")
        _start_conversion_background(
            project_id, output_path, project_dir, output_width, inference_width
        )

        return VideoUploadCompleteResponse(
            project_id=project_id,
            video_path=str(output_path),
            file_size=file_size,
            message="Video upload completed successfully. Image conversion in progress.",
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


@router.post("/projects/{project_id}/trim", response_model=ProjectResponse)
async def set_trim_range(
    project_id: UUID,
    trim_start: float,
    trim_end: float,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update the project's trim range with basic validation.

    Args:
        project_id: ID of the project
        trim_start: Start position in seconds
        trim_end: End position in seconds (must be greater than start)
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
) -> FileResponse:
    """Return a pre-generated JPEG frame from output directory for the given time."""
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not db_project.video_path:
            raise HTTPException(status_code=404, detail="No video for project")

        # Get video info to map time to frame index
        info = get_video_info(Path(db_project.video_path))
        fps = max(info.fps, 1.0)
        frame_index = int(max(0.0, float(time_sec)) * fps)
        frame_index = min(frame_index, max(info.frame_count - 1, 0))

        # Load pre-generated JPEG from output folder
        frame_path = (
            Path(settings.PROJECTS_ROOT_DIR)
            / str(project_id)
            / "output"
            / f"frame_{frame_index:06d}.jpg"
        )
        if not frame_path.exists():
            raise HTTPException(status_code=404, detail="Frame not yet generated")
        return FileResponse(str(frame_path), media_type="image/jpeg")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preview for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get preview") from e


@router.get("/projects/{project_id}/thumbnail")
async def get_thumbnail(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Return the pre-generated thumbnail for project cards.

    Returns a 320px wide JPEG thumbnail generated when video conversion completed.
    Used for quick-loading project card previews.
    """
    # Check if thumbnail exists on disk
    thumbnail_path = Path(settings.PROJECTS_ROOT_DIR) / str(project_id) / "thumbnail.jpg"

    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    return FileResponse(
        str(thumbnail_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/projects/{project_id}/video_info")
async def video_info(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
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


@router.get("/projects/{project_id}/conversion/progress")
async def get_conversion_progress(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get current conversion progress for a project.

    Returns progress information for in-progress JPEG conversion.
    Used by frontend to update progress bar during image conversion phase.

    Args:
        project_id: ID of the project
        db: Database session dependency

    Returns:
        dict: {"saved": int, "total": int, "error": bool, "complete": bool} - frames converted so far
    """
    project_id_str = str(project_id)
    progress = _conversion_progress.get(project_id_str, {"saved": 0, "total": 0, "error": False})
    logger.info(f"Conversion progress: {progress}")

    # Check if conversion is complete by looking for thumbnail file
    # (thumbnail is generated at the end of conversion)
    thumbnail_path = Path(settings.PROJECTS_ROOT_DIR) / project_id_str / "thumbnail.jpg"
    complete = thumbnail_path.exists()

    return {
        "saved": progress["saved"],
        "total": progress["total"],
        "error": progress["error"],
        "complete": complete,
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
