from pathlib import Path
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.projects.shared_objects import conversion_progress, router
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)


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
    progress = conversion_progress.get(project_id_str, {"saved": 0, "total": 0, "error": False})
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
