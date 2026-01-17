"""Aggregate frame status information for a project."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import FrameStatus, FrameStatusAggregateResponse, FrameStatusSummary
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image
from app.models.label import Label
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.get("/projects/{project_id}/frame-statuses", response_model=FrameStatusAggregateResponse)
async def get_frame_statuses(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FrameStatusAggregateResponse:
    """Return per-frame status data and summary counts for a project."""
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        bounds = get_trim_frame_bounds(db_project)
        query = select(Image).where(Image.project_id == project_id)
        if bounds:
            start_frame, end_frame = bounds
            query = query.where(
                Image.frame_number >= start_frame,
                Image.frame_number <= end_frame,
            )
        images_result = await db.execute(query.order_by(Image.frame_number))
        images = list(images_result.scalars().all())

        mask_result = await db.execute(
            select(Mask.image_id).join(Image, Mask.image_id == Image.id).where(
                Image.project_id == project_id
            )
        )
        mask_image_ids = set(mask_result.scalars().all())

        labels_count = await db.scalar(select(func.count()).select_from(Label)) or 0

        frames: list[FrameStatus] = []
        manual_frames = 0
        propagated_frames = 0
        validated_frames = 0
        failed_frames = 0
        unlabeled_frames = 0

        for img in images:
            has_mask = img.id in mask_image_ids
            if img.manually_labeled:
                manual_frames += 1
            elif has_mask:
                propagated_frames += 1
            else:
                unlabeled_frames += 1

            if img.validation == "passed":
                validated_frames += 1
            elif img.validation == "failed":
                failed_frames += 1

            frames.append(
                FrameStatus(
                    frame_number=img.frame_number,
                    status=img.status,
                    manually_labeled=img.manually_labeled,
                    validation=img.validation,
                    has_mask=has_mask,
                )
            )

        summary = FrameStatusSummary(
            total_frames=len(images),
            manual_frames=manual_frames,
            propagated_frames=propagated_frames,
            validated_frames=validated_frames,
            failed_frames=failed_frames,
            unlabeled_frames=unlabeled_frames,
            labels_count=labels_count,
        )

        return FrameStatusAggregateResponse(frames=frames, summary=summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get frame statuses for project %s: %s", project_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get frame status aggregates",
        ) from e
