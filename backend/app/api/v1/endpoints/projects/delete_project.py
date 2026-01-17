"""Delete a project and its associated data."""

from pathlib import Path
import shutil
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.project import Project

from .shared_objects import conversion_progress, router, upload_service

logger = get_logger(__name__)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a project and remove its filesystem data.

    Args:
        project_id: ID of the project to delete
        db: Database session dependency

    Returns:
        dict: Confirmation message

    Raises:
        HTTPException: If project not found or deletion fails
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Cancel any active upload session
        upload_service.cancel_upload(str(project_id))

        await db.delete(db_project)
        await db.commit()

        # Clear any in-memory progress tracking
        conversion_progress.pop(str(project_id), None)

        # Remove project files (best-effort)
        project_dir = Path(settings.PROJECTS_ROOT_DIR) / str(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)

        logger.info(f"Deleted project {project_id}")
        return {"project_id": str(project_id), "message": "Project deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project",
        ) from e
