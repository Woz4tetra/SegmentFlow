"""Set the project-wide crop rectangle and re-extract frames.

The crop is baked into the extracted JPEGs rather than applied at serve time, so every
downstream stage (manual labeling, SAM3 propagation, validation, export) sees the cropped
frames without any coordinate translation. Because mask coordinates live in the inference
image's pixel space, changing the crop invalidates them, so existing masks and labeled points
are cleared when the crop changes.
"""

from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import CropRegionRequest, ProjectResponse
from app.core.config import settings
from app.core.crop_utils import MIN_CROP_PIXELS, CropRect, get_project_crop
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.video_frames import get_video_info
from app.models.image import Image, ValidationStatus
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project

from .complete_video_upload import start_conversion_background
from .shared_objects import conversion_progress, router

logger = get_logger(__name__)


@router.post(
    "/projects/{project_id}/crop",
    response_model=ProjectResponse,
    summary="Set the project crop rectangle",
    description=(
        "Store a normalized crop rectangle that applies to every frame of the video and "
        "re-extract all frames. Existing masks and labeled points are cleared because their "
        "coordinates no longer match the new frames. Send all null fields to clear the crop."
    ),
)
async def set_crop_region(
    project_id: UUID,
    request: CropRegionRequest,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Set or clear the project's crop rectangle.

    Args:
        project_id: ID of the project
        request: Normalized crop rectangle, or all-null to clear the crop
        db: Database session dependency

    Returns:
        ProjectResponse: The updated project

    Raises:
        HTTPException: If the project or video is missing, or the rectangle is invalid
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )
        if not db_project.video_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No video for project",
            )

        video_path = Path(db_project.video_path)
        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file is missing from disk",
            )

        new_crop = _validate_crop(request, video_path)
        current_crop = get_project_crop(db_project)

        if new_crop == current_crop:
            logger.info(f"Crop unchanged for project {project_id}, skipping re-conversion")
            return ProjectResponse.model_validate(db_project)

        db_project.crop_x = new_crop.x if new_crop else None
        db_project.crop_y = new_crop.y if new_crop else None
        db_project.crop_width = new_crop.width if new_crop else None
        db_project.crop_height = new_crop.height if new_crop else None
        db.add(db_project)

        cleared_masks, cleared_points = await _clear_project_annotations(db, project_id)

        await db.commit()
        await db.refresh(db_project)

        project_dir = Path(settings.PROJECTS_ROOT_DIR) / str(project_id)

        # The conversion progress endpoint treats the thumbnail as the "conversion complete"
        # marker, so remove it before kicking off the re-extraction.
        thumbnail_path = project_dir / "thumbnail.jpg"
        thumbnail_path.unlink(missing_ok=True)
        conversion_progress[str(project_id)] = {"saved": 0, "total": 0, "error": False}

        logger.info(
            f"Crop set for project {project_id} to {new_crop}; cleared {cleared_masks} masks "
            f"and {cleared_points} labeled points, starting re-conversion"
        )

        start_conversion_background(
            project_id,
            video_path,
            project_dir,
            settings.OUTPUT_WIDTH,
            settings.INFERENCE_WIDTH,
            db_project.desired_frame_rate,
            new_crop,
        )

        return ProjectResponse.model_validate(db_project)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to set crop for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set crop region",
        ) from e


def _validate_crop(request: CropRegionRequest, video_path: Path) -> CropRect | None:
    """Validate a crop request against the source video dimensions.

    Args:
        request: Incoming crop rectangle
        video_path: Path to the source video

    Returns:
        CropRect | None: Validated rectangle, or None when the request clears the crop

    Raises:
        HTTPException: If the rectangle is partially specified, out of bounds, or too small
    """
    if request.is_cleared():
        return None

    values = (request.x, request.y, request.width, request.height)
    if any(value is None for value in values):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Crop requires x, y, width and height together, or all null to clear",
        )

    x, y, width, height = (float(value) for value in values)  # type: ignore[arg-type]
    if x + width > 1.0 or y + height > 1.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Crop rectangle extends past the frame boundary",
        )

    info = get_video_info(video_path)
    if info.width <= 0 or info.height <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not read source video dimensions",
        )

    crop_pixel_width = round(width * info.width)
    crop_pixel_height = round(height * info.height)
    if crop_pixel_width < MIN_CROP_PIXELS or crop_pixel_height < MIN_CROP_PIXELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Crop must be at least {MIN_CROP_PIXELS}x{MIN_CROP_PIXELS} source pixels "
                f"(got {crop_pixel_width}x{crop_pixel_height})"
            ),
        )

    return CropRect(x=x, y=y, width=width, height=height)


async def _clear_project_annotations(db: AsyncSession, project_id: UUID) -> tuple[int, int]:
    """Delete every mask and labeled point in a project and reset frame flags.

    Args:
        db: Database session
        project_id: ID of the project

    Returns:
        tuple: (masks deleted, labeled points deleted)
    """
    image_ids = list(
        (await db.execute(select(Image.id).where(Image.project_id == project_id))).scalars().all()
    )
    if not image_ids:
        return 0, 0

    mask_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Mask).where(Mask.image_id.in_(image_ids))
            )
        ).scalar_one()
    )
    point_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(LabeledPoint)
                .where(LabeledPoint.image_id.in_(image_ids))
            )
        ).scalar_one()
    )

    await db.execute(delete(Mask).where(Mask.image_id.in_(image_ids)))
    await db.execute(delete(LabeledPoint).where(LabeledPoint.image_id.in_(image_ids)))

    await db.execute(
        update(Image)
        .where(Image.id.in_(image_ids))
        .values(
            manually_labeled=False,
            validation=ValidationStatus.NOT_VALIDATED.value,
        )
    )

    return mask_count, point_count
