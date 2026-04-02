"""Import project videos directly from BrettZone."""

import asyncio
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.projects.complete_video_upload import convert_video_task
from app.api.v1.schemas import BrettzoneImportRequest, BrettzoneImportResponse, ProjectResponse
from app.core.brettzone import discover_entry_from_url, discover_random_entry, download_video
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.project import Project, ProjectStage

from .shared_objects import conversion_progress, router

logger = get_logger(__name__)


@router.post(
    "/projects/import/brettzone",
    response_model=BrettzoneImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_brettzone_video(
    payload: BrettzoneImportRequest,
    db: AsyncSession = Depends(get_db),
) -> BrettzoneImportResponse:
    """Create a new project and import its video from BrettZone."""
    try:
        if not payload.lucky and not payload.brettzone_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide a BrettZone URL or enable lucky mode.",
            )

        if payload.lucky:
            entry = await asyncio.to_thread(discover_random_entry)
        else:
            entry = await asyncio.to_thread(discover_entry_from_url, payload.brettzone_url or "")
        project_name = payload.project_name or _derive_project_name(entry.fight_url, entry.camera)
        project = Project(name=project_name, active=True)
        db.add(project)
        await db.flush()

        output_path = _project_video_path(project.id, entry.media_url)
        file_size = await asyncio.to_thread(download_video, entry.media_url, output_path)

        project.video_path = str(output_path)
        project.stage = ProjectStage.TRIM.value
        db.add(project)
        await db.commit()
        await db.refresh(project)

        _start_conversion_background(
            project_id=project.id,
            video_path=output_path,
            project_dir=Path(settings.PROJECTS_ROOT_DIR) / str(project.id),
            output_width=settings.OUTPUT_WIDTH,
            inference_width=settings.INFERENCE_WIDTH,
        )

        return BrettzoneImportResponse(
            project=ProjectResponse.model_validate(project),
            fight_url=entry.fight_url,
            media_url=entry.media_url,
            camera=entry.camera,
            file_size=file_size,
            message="BrettZone video imported successfully. Image conversion in progress.",
        )
    except HTTPException:
        raise
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (URLError, HTTPError, OSError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach BrettZone. Please try again or use a direct URL.",
        ) from exc
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to import BrettZone video: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import video from BrettZone.",
        ) from exc


def _derive_project_name(fight_url: str, camera: str) -> str:
    url_slug = fight_url.split("?", 1)[-1].replace("&", "_").replace("=", "-")
    safe_slug = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in url_slug)[:120]
    safe_camera = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in camera)[:40]
    return f"BrettZone_{safe_slug}_{safe_camera}".strip("_") or "BrettZone Import"


def _project_video_path(project_id: UUID, media_url: str) -> Path:
    projects_root = Path(settings.PROJECTS_ROOT_DIR)
    project_dir = projects_root / str(project_id)
    videos_dir = project_dir / "videos"
    ext = Path(media_url).suffix.lower()
    if ext not in {".mp4", ".mov", ".avi"}:
        ext = ".mp4"
    return videos_dir / f"original{ext}"


def _start_conversion_background(
    project_id: UUID,
    video_path: Path,
    project_dir: Path,
    output_width: int,
    inference_width: int,
) -> None:
    project_id_str = str(project_id)
    conversion_progress[project_id_str] = {"saved": 0, "total": 0, "error": False}
    thread = threading.Thread(
        target=convert_video_task,
        args=(project_id, video_path, project_dir, output_width, inference_width),
        daemon=True,
    )
    thread.start()
    logger.info("Background conversion thread started for BrettZone import %s", project_id)
