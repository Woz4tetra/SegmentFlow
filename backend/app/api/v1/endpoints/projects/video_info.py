from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.video_frames import get_video_info
from app.models.project import Project

from .shared_objects import router


@router.get("/projects/{project_id}/video_info")
async def video_info(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return basic video metadata: fps, frame_count, width, height, duration."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not db_project.video_path:
        raise HTTPException(status_code=404, detail="No video for project")
    info = get_video_info(Path(db_project.video_path))
    duration = (info.frame_count / info.fps) if info.fps > 0 else 0.0
    return {
        "fps": info.fps,
        "frame_count": info.frame_count,
        "width": info.width,
        "height": info.height,
        "duration": duration,
    }
