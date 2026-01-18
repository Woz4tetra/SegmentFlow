"""Shared objects for propagation endpoints.

This module contains the router, global job tracking, and helper functions
used across all propagation endpoints.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    PropagationProgressUpdate,
    PropagationSegment,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.sam3_state import get_primary_tracker
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image, ValidationStatus
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project

logger = get_logger(__name__)

router = APIRouter()

# Global job tracking
propagation_jobs: dict[str, dict[str, Any]] = {}
job_websockets: dict[str, list[WebSocket]] = {}
job_lock = asyncio.Lock()

# Track background tasks to prevent garbage collection
background_tasks: set[asyncio.Task[None]] = set()


def mask_to_contour(mask: np.ndarray) -> tuple[list[list[float]], float]:
    """Convert a binary mask to a contour polygon and calculate area.

    Args:
        mask: Binary mask array (2D or 3D boolean or uint8). Extra dimensions are squeezed.

    Returns:
        Tuple of (contour_polygon, area) where contour_polygon is [[x, y], ...]
    """
    # Squeeze extra dimensions (SAM3 may return masks with shape (1, H, W) or (H, W))
    mask_2d = np.squeeze(mask)

    # Ensure we have a 2D array
    if mask_2d.ndim != 2:
        logger.warning(f"Unexpected mask shape after squeeze: {mask_2d.shape}, expected 2D")
        return [], 0.0

    # Ensure mask is uint8 and contiguous
    if mask_2d.dtype == bool:
        mask_uint8 = mask_2d.astype(np.uint8) * 255
    else:
        mask_uint8 = mask_2d.astype(np.uint8)

    # Ensure contiguous memory layout for OpenCV
    mask_uint8 = np.ascontiguousarray(mask_uint8)

    # Find contours
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return [], 0.0

    # Get the largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(largest_contour))

    # Convert to list of [x, y] coordinates
    contour_polygon = [[float(pt[0][0]), float(pt[0][1])] for pt in largest_contour]

    return contour_polygon, area


async def get_labeled_frames(
    project_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[list[int], dict[int, Image]]:
    """Get all manually labeled frames for a project.

    Args:
        project_id: UUID of the project
        db: Database session

    Returns:
        Tuple of (labeled_frame_numbers, labeled_images_dict)
    """
    result = await db.execute(
        select(Image).where(Image.project_id == project_id).order_by(Image.frame_number)
    )
    images = result.scalars().all()

    labeled_frame_numbers = []
    labeled_images: dict[int, Image] = {}

    for img in images:
        if img.manually_labeled:
            labeled_frame_numbers.append(img.frame_number)
            labeled_images[img.frame_number] = img

    return labeled_frame_numbers, labeled_images


async def build_source_frames_data(
    labeled_frame_numbers: list[int],
    labeled_images: dict[int, Image],
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Build source frame data with points for each labeled frame.

    Args:
        labeled_frame_numbers: List of labeled frame numbers
        labeled_images: Dict mapping frame number to Image
        db: Database session

    Returns:
        List of source frame data dicts
    """
    source_frames_data = []

    for frame_num in labeled_frame_numbers:
        img = labeled_images[frame_num]

        # Get points for this image
        points_result = await db.execute(
            select(LabeledPoint).where(LabeledPoint.image_id == img.id)
        )
        points = points_result.scalars().all()

        # Group points by label
        points_by_label: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for pt in points:
            if pt.label_id not in points_by_label:
                points_by_label[pt.label_id] = []
            points_by_label[pt.label_id].append(
                {
                    "x": pt.x,
                    "y": pt.y,
                    "include": pt.include,
                }
            )

        source_frames_data.append(
            {
                "frame_number": frame_num,
                "image_id": img.id,
                "points_by_label": points_by_label,
            }
        )

    return source_frames_data


def _is_frame_eligible(
    img: Image,
    has_masks: bool,
    source_updated_at: datetime | None,
    mask_updated_at: datetime | None,
) -> bool:
    if not has_masks:
        return True
    if img.validation != ValidationStatus.FAILED.value:
        return False
    if not source_updated_at or not mask_updated_at:
        return False
    return source_updated_at > mask_updated_at


def build_propagation_segments(
    images_by_frame: dict[int, Image],
    labeled_frame_numbers: list[int],
    max_propagation_length: int,
    has_mask_by_frame: dict[int, bool],
    source_updated_by_frame: dict[int, datetime],
    mask_updated_by_frame: dict[int, datetime],
    max_frame: int,
) -> list[PropagationSegment]:
    """Build propagation segments from labeled frames with filtering rules.

    Frames are eligible when they are within the propagation limit from a previous
    manually labeled image and either have no masks or are marked as validation failed.

    Args:
        images_by_frame: Map of frame number to Image
        labeled_frame_numbers: Sorted list of labeled frame numbers
        max_propagation_length: Maximum frames per segment
        has_mask_by_frame: Map of frame number to mask presence
        max_frame: Maximum frame number in project

    Returns:
        List of PropagationSegment objects
    """
    segments: list[PropagationSegment] = []

    for i, labeled_frame in enumerate(labeled_frame_numbers):
        if i < len(labeled_frame_numbers) - 1:
            next_labeled = labeled_frame_numbers[i + 1]
            end_frame = min(labeled_frame + max_propagation_length, next_labeled - 1)
        else:
            end_frame = min(labeled_frame + max_propagation_length, max_frame)

        if end_frame <= labeled_frame:
            continue

        eligible_frames: list[int] = []
        source_updated_at = source_updated_by_frame.get(labeled_frame)
        for frame in range(labeled_frame + 1, end_frame + 1):
            img = images_by_frame.get(frame)
            if not img or img.manually_labeled:
                continue
            has_masks = has_mask_by_frame.get(frame, False)
            if _is_frame_eligible(
                img,
                has_masks,
                source_updated_at,
                mask_updated_by_frame.get(frame),
            ):
                eligible_frames.append(frame)

        if not eligible_frames:
            continue

        start_frame = eligible_frames[0]
        prev_frame = eligible_frames[0]
        for frame in eligible_frames[1:]:
            if frame == prev_frame + 1:
                prev_frame = frame
                continue
            segments.append(
                PropagationSegment(
                    start_frame=start_frame,
                    end_frame=prev_frame,
                    source_frame=labeled_frame,
                    direction="forward",
                    num_frames=prev_frame - start_frame + 1,
                )
            )
            start_frame = frame
            prev_frame = frame

        segments.append(
                PropagationSegment(
                        start_frame=start_frame,
                end_frame=prev_frame,
                        source_frame=labeled_frame,
                direction="forward",
                num_frames=prev_frame - start_frame + 1,
                    )
                )

    return segments


async def analyze_propagation_segments(
    project_id: uuid.UUID,
    db: AsyncSession,
    max_propagation_length: int,
) -> tuple[list[PropagationSegment], list[dict[str, Any]]]:
    """Analyze manually labeled frames and determine propagation segments.

    Args:
        project_id: UUID of the project
        db: Database session
        max_propagation_length: Maximum frames per propagation segment

    Returns:
        Tuple of (segments, source_frames_data)
    """
    # Get all images for the project
    result = await db.execute(
        select(Image).where(Image.project_id == project_id).order_by(Image.frame_number)
    )
    images = list(result.scalars().all())

    if not images:
        return [], []

    # Apply trim range filter if set
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    bounds = get_trim_frame_bounds(project) if project else None
    if bounds:
        start_frame, end_frame = bounds
        images = [img for img in images if start_frame <= img.frame_number <= end_frame]
    if not images:
        return [], []

    # Get labeled frames
    labeled_frame_numbers, labeled_images = await get_labeled_frames(project_id, db)
    if bounds:
        labeled_frame_numbers = [f for f in labeled_frame_numbers if start_frame <= f <= end_frame]
        labeled_images = {f: labeled_images[f] for f in labeled_frame_numbers if f in labeled_images}

    if len(labeled_frame_numbers) < 1:
        return [], []

    # Get frame boundaries
    all_frame_numbers = [img.frame_number for img in images]
    max_frame = max(all_frame_numbers)

    # Build source frames data
    source_frames_data = await build_source_frames_data(labeled_frame_numbers, labeled_images, db)

    # Build mask presence map for filtering
    mask_result = await db.execute(
        select(Mask.image_id, func.max(Mask.updated_at))
        .join(Image, Mask.image_id == Image.id)
        .where(Image.project_id == project_id)
        .group_by(Mask.image_id)
    )
    mask_updated_by_image_id = {row[0]: row[1] for row in mask_result.all()}
    images_by_frame = {img.frame_number: img for img in images}
    has_mask_by_frame = {img.frame_number: (img.id in mask_updated_by_image_id) for img in images}
    mask_updated_by_frame = {
        img.frame_number: mask_updated_by_image_id.get(img.id) for img in images
    }

    source_points_result = await db.execute(
        select(Image.frame_number, func.max(LabeledPoint.updated_at))
        .join(LabeledPoint, LabeledPoint.image_id == Image.id)
        .where(Image.project_id == project_id)
        .group_by(Image.frame_number)
    )
    source_updated_by_frame = {row[0]: row[1] for row in source_points_result.all()}
    for img in images:
        if img.manually_labeled and img.frame_number not in source_updated_by_frame:
            source_updated_by_frame[img.frame_number] = img.updated_at

    # Sort and build segments
    labeled_frame_numbers.sort()
    segments = build_propagation_segments(
        images_by_frame,
        labeled_frame_numbers,
        max_propagation_length,
        has_mask_by_frame,
        source_updated_by_frame,
        mask_updated_by_frame,
        max_frame,
    )

    return segments, source_frames_data


async def save_segment_masks(
    video_segments: dict[int, dict[int, np.ndarray]],
    label_id_to_obj_id: dict[uuid.UUID, int],
    source_frame: int,
    project_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Save propagated masks for a segment to the database.

    Args:
        video_segments: Dict of {frame_idx: {obj_id: mask}}
        label_id_to_obj_id: Mapping from label_id to obj_id
        source_frame: Source frame number (to skip)
        project_id: Project UUID
        db: Database session
    """
    # Get all images for this project
    images_result = await db.execute(select(Image).where(Image.project_id == project_id))
    images_by_frame = {img.frame_number: img for img in images_result.scalars().all()}

    # Save masks for each frame
    for frame_idx, obj_masks in video_segments.items():
        # Skip source frame (already has masks)
        if frame_idx == source_frame:
            continue

        image = images_by_frame.get(frame_idx)
        if not image:
            continue

        for obj_id, mask in obj_masks.items():
            # Find label_id for this obj_id
            label_id = next(
                (lid for lid, oid in label_id_to_obj_id.items() if oid == obj_id),
                None,
            )
            if label_id is None:
                continue

            # Convert mask to contour
            contour_polygon, area = mask_to_contour(mask)
            if not contour_polygon:
                continue

            # Delete existing mask for this image/label
            existing_result = await db.execute(
                select(Mask).where(
                    Mask.image_id == image.id,
                    Mask.label_id == label_id,
                )
            )
            existing_mask = existing_result.scalar_one_or_none()
            if existing_mask:
                await db.delete(existing_mask)

            # Create new mask
            new_mask = Mask(
                image_id=image.id,
                label_id=label_id,
                contour_polygon=contour_polygon,
                area=area,
            )
            db.add(new_mask)

            # Set validation status to not_validated
            image.validation = ValidationStatus.NOT_VALIDATED.value

    await db.commit()


def create_progress_callback(
    job_id: str,
    project_id: uuid.UUID,
    job: dict[str, Any],
    seg_idx: int,
    segment: PropagationSegment,
    segments: list[PropagationSegment],
    total_frames: int,
    frames_completed_ref: list[int],
    start_time: float,
    loop: asyncio.AbstractEventLoop,
) -> Callable[[int, float], None]:
    """Create a progress callback for a segment.

    Args:
        job_id: Job identifier
        project_id: Project UUID
        job: Job dict reference
        seg_idx: Current segment index
        segment: Current segment
        segments: All segments
        total_frames: Total frames to process
        frames_completed_ref: Mutable reference to frames completed count
        start_time: Job start time
        loop: Event loop to schedule broadcasts on (for thread-safety)

    Returns:
        Progress callback function
    """

    def progress_callback(frame_idx: int, progress: float) -> None:
        elapsed = time.perf_counter() - start_time
        frames_done = frames_completed_ref[0] + int(progress * segment.num_frames)
        rate = frames_done / elapsed if elapsed > 0 else 1
        remaining = (total_frames - frames_done) / rate if rate > 0 else 0

        update = PropagationProgressUpdate(
            job_id=job_id,
            project_id=project_id,
            status="running",
            current_segment=seg_idx + 1,
            total_segments=len(segments),
            current_frame=frame_idx,
            frames_completed=frames_done,
            total_frames=total_frames,
            progress_percent=(frames_done / total_frames) * 100 if total_frames > 0 else 0,
            estimated_remaining_ms=remaining * 1000,
            error=None,
        )
        job["progress"] = update

        # Send to connected websockets - use thread-safe scheduling since
        # this callback is called from run_in_executor (thread pool)
        def schedule_broadcast() -> None:
            task = asyncio.create_task(broadcast_progress(job_id, update))
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        loop.call_soon_threadsafe(schedule_broadcast)

    return progress_callback


async def process_segment(
    segment: PropagationSegment,
    seg_idx: int,
    segments: list[PropagationSegment],
    source_data_by_frame: dict[int, dict[str, Any]],
    job_id: str,
    project_id: uuid.UUID,
    job: dict[str, Any],
    total_frames: int,
    frames_completed_ref: list[int],
    start_time: float,
    tracker: Any,
    db_factory: Callable[[], AsyncGenerator[AsyncSession, None]],
) -> None:
    """Process a single propagation segment.

    Args:
        segment: Segment to process
        seg_idx: Segment index
        segments: All segments
        source_data_by_frame: Source frame data lookup
        job_id: Job identifier
        project_id: Project UUID
        job: Job dict reference
        total_frames: Total frames
        frames_completed_ref: Mutable frames completed count
        start_time: Job start time
        tracker: SAM3 tracker
        db_factory: Database session factory
    """
    source_data = source_data_by_frame.get(segment.source_frame)
    if not source_data:
        logger.warning(f"No source data for frame {segment.source_frame}, skipping segment")
        return

    # Build points_by_obj dict for SAM3
    points_by_obj: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    label_id_to_obj_id: dict[uuid.UUID, int] = {}

    for label_id, points in source_data["points_by_label"].items():
        if not points:
            continue

        obj_id = hash(str(label_id))
        label_id_to_obj_id[label_id] = obj_id

        pts_array = np.array([[p["x"], p["y"]] for p in points], dtype=np.float32)
        labels_array = np.array([1 if p["include"] else 0 for p in points], dtype=np.int32)
        points_by_obj[obj_id] = (pts_array, labels_array)

    if not points_by_obj:
        logger.warning(f"No points for segment from frame {segment.source_frame}, skipping")
        return

    # Determine propagation range
    if segment.direction == "forward":
        propagate_length = segment.end_frame - segment.source_frame + 1
    else:
        propagate_length = segment.source_frame - segment.start_frame + 1

    # Get event loop before creating callback (needed for thread-safe scheduling)
    loop = asyncio.get_event_loop()

    # Create progress callback
    progress_callback = create_progress_callback(
        job_id,
        project_id,
        job,
        seg_idx,
        segment,
        segments,
        total_frames,
        frames_completed_ref,
        start_time,
        loop,
    )

    # Run propagation
    logger.info(
        f"Propagating segment {seg_idx + 1}/{len(segments)}: "
        f"frame {segment.source_frame} -> {segment.start_frame}-{segment.end_frame} "
        f"({segment.direction})"
    )

    video_segments, _original_frames = await loop.run_in_executor(
        None,
        tracker.propagate_from_frame,
        segment.source_frame,
        points_by_obj,
        propagate_length,
        progress_callback,
    )

    # Save propagated masks to database
    async for db in db_factory():
        await save_segment_masks(
            video_segments,
            label_id_to_obj_id,
            segment.source_frame,
            project_id,
            db,
        )
        await db.close()
        return  # Only process one session

    frames_completed_ref[0] += segment.num_frames


async def run_propagation_job(
    job_id: str,
    project_id: uuid.UUID,
    segments: list[PropagationSegment],
    source_frames_data: list[dict[str, Any]],
    db_factory: Callable[[], AsyncGenerator[AsyncSession, None]],
) -> None:
    """Run the propagation job in a background task.

    Args:
        job_id: Unique job identifier
        project_id: UUID of the project
        segments: List of propagation segments
        source_frames_data: Data about source frames with their points
        db_factory: Factory function to create database sessions
    """
    job = propagation_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow()

    total_frames = sum(seg.num_frames for seg in segments)
    frames_completed_ref = [0]  # Use list for mutable reference
    start_time = time.perf_counter()

    try:
        # Get SAM3 tracker
        tracker = get_primary_tracker()
        if tracker is None:
            raise RuntimeError("SAM3 model not initialized")

        # Get project directory
        project_dir = Path(settings.PROJECTS_ROOT_DIR) / str(project_id)
        inference_dir = project_dir / "inference"

        if not inference_dir.exists():
            raise RuntimeError(f"Inference directory not found: {inference_dir}")

        # Set images directory for tracker
        tracker.set_images_dir(str(inference_dir))

        # Build lookup for source frame data
        source_data_by_frame = {sf["frame_number"]: sf for sf in source_frames_data}

        # Process each segment
        for seg_idx, segment in enumerate(segments):
            await process_segment(
                segment,
                seg_idx,
                segments,
                source_data_by_frame,
                job_id,
                project_id,
                job,
                total_frames,
                frames_completed_ref,
                start_time,
                tracker,
                db_factory,
            )
            frames_completed_ref[0] += segment.num_frames

        # Job completed successfully
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow()

        final_update = PropagationProgressUpdate(
            job_id=job_id,
            project_id=project_id,
            status="completed",
            current_segment=len(segments),
            total_segments=len(segments),
            current_frame=0,
            frames_completed=total_frames,
            total_frames=total_frames,
            progress_percent=100.0,
            estimated_remaining_ms=0,
            error=None,
        )
        job["progress"] = final_update
        await broadcast_progress(job_id, final_update)

        # Update project stage to propagation
        async for db in db_factory():
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if project:
                project.stage = "propagation"
                project.propagation_visited = True
                await db.commit()
            await db.close()
            return  # Only process one session

        logger.info(f"Propagation job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Propagation job {job_id} failed: {e}", exc_info=True)
        job["status"] = "failed"
        job["error"] = str(e)

        error_update = PropagationProgressUpdate(
            job_id=job_id,
            project_id=project_id,
            status="failed",
            current_segment=0,
            total_segments=len(segments),
            current_frame=0,
            frames_completed=frames_completed_ref[0],
            total_frames=total_frames,
            progress_percent=(frames_completed_ref[0] / total_frames) * 100
            if total_frames > 0
            else 0,
            estimated_remaining_ms=0,
            error=str(e),
        )
        job["progress"] = error_update
        await broadcast_progress(job_id, error_update)


async def broadcast_progress(job_id: str, update: PropagationProgressUpdate) -> None:
    """Broadcast progress update to all connected WebSocket clients for a job.

    Args:
        job_id: Job identifier
        update: Progress update to send
    """
    if job_id not in job_websockets:
        return

    # Send to all connected clients
    disconnected = []
    for ws in job_websockets[job_id]:
        try:
            await ws.send_json(update.model_dump(mode="json"))
        except Exception:
            disconnected.append(ws)

    # Clean up disconnected clients
    for ws in disconnected:
        job_websockets[job_id].remove(ws)
