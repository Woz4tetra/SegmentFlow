"""Serve an uncropped frame decoded straight from the source video.

The Trim page's crop selector needs the full source frame. It cannot use the pre-generated
output frames because those already have the current crop baked in, which would make a crop
impossible to widen once applied.
"""

from pathlib import Path
from uuid import UUID

import cv2
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.video_frames import get_video_info, read_frame_at_index, resize_to_width
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


@router.get("/projects/{project_id}/source_frame")
async def get_source_frame(
    project_id: UUID,
    time_sec: float,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the uncropped source frame at the given time as a JPEG.

    Args:
        project_id: ID of the project
        time_sec: Position in the video, in seconds
        db: Database session dependency

    Returns:
        Response: JPEG image bytes

    Raises:
        HTTPException: If the project, video, or frame is unavailable
    """
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        db_project = result.scalar_one_or_none()
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not db_project.video_path:
            raise HTTPException(status_code=404, detail="No video for project")

        video_path = Path(db_project.video_path)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Original video not available")

        info = get_video_info(video_path)
        fps = max(info.fps, 1.0)
        frame_index = int(max(0.0, float(time_sec)) * fps)

        frame = read_frame_at_index(video_path, frame_index)
        if frame is None:
            raise HTTPException(status_code=404, detail="Frame could not be read")

        # Never upscale: the selector only needs enough detail to position the rectangle
        frame = resize_to_width(frame, min(settings.OUTPUT_WIDTH, frame.shape[1]))
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to encode frame")

        return Response(
            content=buf.tobytes(),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=300"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source frame for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get source frame") from e
