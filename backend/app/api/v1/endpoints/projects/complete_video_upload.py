import threading
from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.v1.endpoints.projects.shared_objects import (
    conversion_progress,
    router,
    upload_service,
)
from app.api.v1.schemas import VideoUploadCompleteResponse
from app.core.config import settings
from app.core.crop_utils import CropRect, get_project_crop
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.video_frames import convert_video_to_jpegs, generate_thumbnail
from app.core.video_transcode import ensure_opencv_readable
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
        start_conversion_background(
            project_id,
            output_path,
            project_dir,
            output_width,
            inference_width,
            db_project.desired_frame_rate,
            get_project_crop(db_project),
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


def _remove_existing_frames(*frame_dirs: Path) -> None:
    """Delete previously extracted frame JPEGs from the given directories.

    Args:
        frame_dirs: Directories holding frame_NNNNNN.jpg files
    """
    for frame_dir in frame_dirs:
        for frame_file in frame_dir.glob("frame_*.jpg"):
            try:
                frame_file.unlink()
            except OSError as e:
                logger.warning(f"[BG] Failed to remove stale frame {frame_file}: {e}")


def convert_video_task(
    project_id: UUID,
    video_path: Path,
    project_dir: Path,
    output_width: int,
    inference_width: int,
    desired_frame_rate: float | None = None,
    crop: CropRect | None = None,
) -> None:
    """Convert video to JPEGs and populate database with Image records.

    This runs in a background thread, so we need to use synchronous database operations.
    Safe to re-run for a project: stale frames are removed first and Image records are
    reconciled rather than blindly inserted.
    """

    project_id_str = str(project_id)
    logger.info(f"[BG] Starting conversion for project {project_id}")
    conversion_progress[project_id_str] = {"saved": 0, "total": 0, "error": False}

    # OpenCV cannot decode every codec we accept (AV1, notably). Normalize first so
    # extraction and the preview endpoints both have something they can read.
    try:
        readable_path = ensure_opencv_readable(video_path)
    except RuntimeError as transcode_err:
        logger.error(f"[BG] Cannot decode video for project {project_id}: {transcode_err}")
        conversion_progress[project_id_str]["error"] = True
        return
    if readable_path != video_path:
        video_path = readable_path
        _update_project_video_path(project_id, readable_path)

    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    inference_dir = project_dir / "inference"
    inference_dir.mkdir(parents=True, exist_ok=True)

    # Remove frames from any previous conversion so a stale frame set cannot survive
    _remove_existing_frames(output_dir, inference_dir)

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
        desired_fps=desired_frame_rate,
        progress_callback=progress_cb,
        crop=crop,
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
        _reconcile_image_records(project_id, output_dir, inference_dir)
    except Exception as db_err:
        logger.error(
            f"[BG] Failed to create Image records for project {project_id}: {db_err}",
            exc_info=db_err,
        )
        conversion_progress[project_id_str]["error"] = True


def _sync_engine() -> Engine:
    """Build a synchronous engine for use from the background conversion thread."""
    db_url = settings.get_database_url()
    if "postgresql+asyncpg" in db_url:
        sync_url = db_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    elif "sqlite+aiosqlite" in db_url:
        sync_url = db_url.replace("sqlite+aiosqlite", "sqlite")
    else:
        sync_url = db_url
    return create_engine(sync_url)


def _update_project_video_path(project_id: UUID, video_path: Path) -> None:
    """Point the project at a different video file, e.g. after a transcode.

    Args:
        project_id: Project UUID
        video_path: Path the project should use from now on
    """
    with Session(_sync_engine()) as session:
        project = session.scalars(select(Project).where(Project.id == project_id)).one_or_none()
        if project is None:
            logger.warning(f"[BG] Project {project_id} vanished before video path update")
            return
        project.video_path = str(video_path)
        session.add(project)
        session.commit()
    logger.info(f"[BG] Project {project_id} now uses video {video_path}")


def _reconcile_image_records(project_id: UUID, output_dir: Path, inference_dir: Path) -> None:
    """Sync the project's Image records with the frames currently on disk.

    Updates existing records, inserts missing ones, and deletes records whose frame file is
    gone, so a re-conversion does not duplicate rows.

    Args:
        project_id: Project UUID
        output_dir: Directory holding the output-resolution frames
        inference_dir: Directory holding the inference-resolution frames
    """
    # Synchronous engine, since this runs in a background thread
    engine = _sync_engine()
    projects_root = Path(settings.PROJECTS_ROOT_DIR)

    with Session(engine) as session:
        inference_files = sorted(inference_dir.glob("frame_*.jpg"))
        output_files = sorted(output_dir.glob("frame_*.jpg"))

        # Existing records keyed by frame number, so a re-conversion updates rather
        # than duplicates them
        existing_images = {
            image.frame_number: image
            for image in session.scalars(select(Image).where(Image.project_id == project_id)).all()
        }

        converted_frame_numbers: set[int] = set()
        for inf_file, out_file in zip(inference_files, output_files, strict=False):
            frame_number = int(inf_file.stem.split("_")[1])
            converted_frame_numbers.add(frame_number)

            # Construct relative paths from project directory
            inf_rel_path = str(inf_file.relative_to(projects_root))
            out_rel_path = str(out_file.relative_to(projects_root))

            image = existing_images.get(frame_number)
            if image is None:
                image = Image(
                    project_id=project_id,
                    frame_number=frame_number,
                    inference_path=inf_rel_path,
                    output_path=out_rel_path,
                    status=ImageStatus.PROCESSED,
                    manually_labeled=False,
                    validation=ValidationStatus.NOT_VALIDATED,
                )
            else:
                image.inference_path = inf_rel_path
                image.output_path = out_rel_path
                image.status = ImageStatus.PROCESSED
            session.add(image)

        # Drop records whose frame no longer exists on disk
        stale_frame_numbers = set(existing_images) - converted_frame_numbers
        for frame_number in stale_frame_numbers:
            session.delete(existing_images[frame_number])

        session.commit()
        logger.info(
            f"[BG] Reconciled {len(converted_frame_numbers)} Image records "
            f"({len(stale_frame_numbers)} removed) for project {project_id}"
        )


def start_conversion_background(
    project_id: UUID,
    video_path: Path,
    project_dir: Path,
    output_width: int,
    inference_width: int,
    desired_frame_rate: float | None = None,
    crop: CropRect | None = None,
) -> None:
    """Start video-to-JPEG conversion in background thread.

    Args:
        project_id: Project UUID
        video_path: Path to video file
        project_dir: Project directory
        output_width: width of the output image
        inference_width: width of the inference image
        desired_frame_rate: optional target frame rate for sampling
        crop: optional normalized crop applied to every frame
    """

    # Start conversion in background thread
    thread = threading.Thread(
        target=convert_video_task,
        args=(
            project_id,
            video_path,
            project_dir,
            output_width,
            inference_width,
            desired_frame_rate,
            crop,
        ),
        daemon=True,
    )
    thread.start()
    logger.info(f"Background conversion thread started for project {project_id}")
