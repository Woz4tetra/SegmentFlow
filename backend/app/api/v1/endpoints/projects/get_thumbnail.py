from pathlib import Path
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

from .shared_objects import router


@router.get("/projects/{project_id}/thumbnail")
async def get_thumbnail(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Return the pre-generated thumbnail for project cards.

    Returns a 320px wide JPEG thumbnail generated when video conversion completed.
    Used for quick-loading project card previews.
    """
    # Check if thumbnail exists on disk
    thumbnail_path = Path(settings.PROJECTS_ROOT_DIR) / str(project_id) / "thumbnail.jpg"

    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    return FileResponse(
        str(thumbnail_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )
