"""Return compact per-frame index data for manual labeling startup."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import FrameIndexEntry, FrameIndexResponse
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.get("/projects/{project_id}/frame-index", response_model=FrameIndexResponse)
async def get_frame_index(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FrameIndexResponse:
    """Return compact frame metadata for manual-labeling navigation."""
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        has_mask_expr = (func.count(Mask.id) > 0).label("has_mask")
        query = (
            select(
                Image.frame_number,
                Image.status,
                Image.manually_labeled,
                Image.validation,
                has_mask_expr,
            )
            .outerjoin(Mask, Mask.image_id == Image.id)
            .where(Image.project_id == project_id)
        )

        bounds = get_trim_frame_bounds(db_project)
        if bounds:
            start_frame, end_frame = bounds
            query = query.where(
                Image.frame_number >= start_frame,
                Image.frame_number <= end_frame,
            )

        query = query.group_by(
            Image.id,
            Image.frame_number,
            Image.status,
            Image.manually_labeled,
            Image.validation,
        ).order_by(Image.frame_number)

        rows = (await db.execute(query)).all()
        frames = [
            FrameIndexEntry(
                frame_number=row.frame_number,
                status=row.status,
                manually_labeled=row.manually_labeled,
                validation=row.validation,
                has_mask=bool(row.has_mask),
            )
            for row in rows
        ]
        return FrameIndexResponse(frames=frames, total=len(frames))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get frame index for project %s: %s", project_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get frame index",
        ) from e
