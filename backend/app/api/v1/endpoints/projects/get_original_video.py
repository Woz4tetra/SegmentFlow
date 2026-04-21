from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project

from .shared_objects import router


@router.get("/projects/{project_id}/original_video")
async def get_original_video(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Return the project's original uploaded video file."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not db_project.video_path:
        raise HTTPException(status_code=404, detail="No video for project")

    video_path = Path(db_project.video_path)
    if not video_path.exists() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Original video not available")

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename="original.mp4",
    )
