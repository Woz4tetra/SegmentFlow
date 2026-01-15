import threading
from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.v1.endpoints.projects.shared_objects import (
    conversion_progress,
    router,
    upload_service,
)
from app.api.v1.schemas import VideoUploadCompleteResponse
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.video_frames import convert_video_to_jpegs, generate_thumbnail
from app.models.image import Image, ImageStatus, ValidationStatus
from app.models.project import Project, ProjectStage

logger = get_logger(__name__)


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
        session = upload_service.get_session(str(project_id))  # scoped use
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
        upload_service.finalize_upload(str(project_id), output_path)

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


def convert_video_task(
    project_id: UUID,
    video_path: Path,
    project_dir: Path,
    output_width: int,
    inference_width: int,
) -> None:
    """Convert video to JPEGs and populate database with Image records.

    This runs in a background thread, so we need to use synchronous database operations.
    """

    project_id_str = str(project_id)
    logger.info(f"[BG] Starting conversion for project {project_id}")
    conversion_progress[project_id_str] = {"saved": 0, "total": 0, "error": False}
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    inference_dir = project_dir / "inference"
    inference_dir.mkdir(parents=True, exist_ok=True)

    def progress_cb(saved: int, total: int) -> None:
        conversion_progress[project_id_str]["saved"] = saved
        conversion_progress[project_id_str]["total"] = total
        logger.debug(f"[BG] Conversion progress {project_id}: {saved}/{total}")

    did_error = convert_video_to_jpegs(
        video_path,
        output_dir,
        inference_dir,
        output_width,
        inference_width,
        progress_callback=progress_cb,
    )
    conversion_progress[project_id_str]["error"] = did_error
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
        conversion_progress[project_id_str]["error"] = True
        return

    # Populate database with Image records
    try:
        logger.info(f"[BG] Creating Image records in database for project {project_id}")

        # Create synchronous database engine for background thread
        # Convert async URL to sync URL
        db_url = settings.get_database_url()
        if "postgresql+asyncpg" in db_url:
            sync_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
        elif "sqlite+aiosqlite" in db_url:
            sync_url = db_url.replace("sqlite+aiosqlite", "sqlite")
        else:
            sync_url = db_url

        engine = create_engine(sync_url)

        with Session(engine) as session:
            # Get all frame files
            inference_files = sorted(inference_dir.glob("frame_*.jpg"))
            output_files = sorted(output_dir.glob("frame_*.jpg"))

            # Create Image records for each frame
            for inf_file, out_file in zip(inference_files, output_files, strict=False):
                frame_number = int(inf_file.stem.split("_")[1])

                # Construct relative paths from project directory
                inf_rel_path = str(inf_file.relative_to(Path(settings.PROJECTS_ROOT_DIR)))
                out_rel_path = str(out_file.relative_to(Path(settings.PROJECTS_ROOT_DIR)))

                image = Image(
                    project_id=project_id,
                    frame_number=frame_number,
                    inference_path=inf_rel_path,
                    output_path=out_rel_path,
                    status=ImageStatus.PROCESSED,
                    manually_labeled=False,
                    validation=ValidationStatus.NOT_VALIDATED,
                )
                session.add(image)

            session.commit()
            logger.info(
                f"[BG] Created {len(inference_files)} Image records for project {project_id}"
            )

    except Exception as db_err:
        logger.error(
            f"[BG] Failed to create Image records for project {project_id}: {db_err}",
            exc_info=db_err,
        )
        conversion_progress[project_id_str]["error"] = True


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
