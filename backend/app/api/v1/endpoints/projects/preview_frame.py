from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.video_frames import get_video_info
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


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
