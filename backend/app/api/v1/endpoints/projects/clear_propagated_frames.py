"""Clear propagated masks for a project.

Deletes masks for non-manually-labeled frames and resets validation status
for those affected frames.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ClearPropagatedFramesResponse
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image, ValidationStatus
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.delete(
    "/projects/{project_id}/propagated-frames",
    response_model=ClearPropagatedFramesResponse,
    summary="Clear propagated frames for a project",
    description=(
        "Delete propagated masks from non-manually-labeled frames and reset "
        "their validation status to not_validated."
    ),
)
async def clear_propagated_frames(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClearPropagatedFramesResponse:
    """Clear propagated masks for all eligible frames in a project."""
    try:
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}",
            )

        image_query = select(Image.id).where(
            Image.project_id == project_id,
            Image.manually_labeled.is_(False),
        )
        bounds = get_trim_frame_bounds(project)
        if bounds:
            start_frame, end_frame = bounds
            image_query = image_query.where(
                Image.frame_number >= start_frame,
                Image.frame_number <= end_frame,
            )

        # Only target frames that currently have masks (propagated output)
        image_query = image_query.where(
            Image.id.in_(select(Mask.image_id).distinct())
        )
        image_ids = list((await db.execute(image_query)).scalars().all())

        if not image_ids:
            return ClearPropagatedFramesResponse(
                success=True,
                project_id=project_id,
                frames_cleared=0,
                masks_deleted=0,
                message="No propagated frames found to clear.",
            )

        delete_result = await db.execute(delete(Mask).where(Mask.image_id.in_(image_ids)))
        masks_deleted = int(delete_result.rowcount or 0)

        await db.execute(
            update(Image)
            .where(Image.id.in_(image_ids))
            .values(validation=ValidationStatus.NOT_VALIDATED.value)
        )
        await db.commit()

        logger.info(
            "Cleared propagated frames for project %s: %s frames, %s masks",
            project_id,
            len(image_ids),
            masks_deleted,
        )

        return ClearPropagatedFramesResponse(
            success=True,
            project_id=project_id,
            frames_cleared=len(image_ids),
            masks_deleted=masks_deleted,
            message="Cleared propagated masks and reset validation on affected frames.",
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to clear propagated frames for project %s: %s", project_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear propagated frames",
        ) from e
