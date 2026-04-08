"""Import project videos directly from BrettZone."""

import asyncio
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import cv2
import numpy as np
from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.projects.complete_video_upload import convert_video_task
from app.api.v1.schemas import BrettzoneImportRequest, BrettzoneImportResponse, ProjectResponse
from app.core.brettzone import discover_entry_from_url, discover_random_entry, download_video
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import resolve_import_trim_bounds
from app.models.label import Label
from app.models.project import Project, ProjectStage
from app.models.project_label_setting import ProjectLabelSetting

from .shared_objects import conversion_progress, router

logger = get_logger(__name__)
THUMBNAIL_SIZE = 128


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
    created_project_id: UUID | None = None
    video_update_applied = False
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
        logger.info(
            "BrettZone import discovery: fight_url=%s camera=%s robots=%s thumbnails=%s",
            entry.fight_url,
            entry.camera,
            entry.robot_names,
            list(entry.robot_thumbnails.keys()),
        )
        project_name = payload.project_name or _derive_project_name(entry.fight_url, entry.camera)
        project = Project(name=project_name, active=True)
        db.add(project)
        await db.flush()
        created_project_id = project.id

        await _ensure_robot_labels_for_project(
            project.id,
            entry.robot_names,
            entry.robot_thumbnails,
            db,
        )
        # Persist project and label settings before slow network/file operations.
        await db.commit()

        output_path = _project_video_path(project.id, entry.media_url)
        file_size = await asyncio.to_thread(download_video, entry.media_url, output_path)
        try:
            trim_bounds = await asyncio.to_thread(
                resolve_import_trim_bounds,
                output_path,
                entry.fight_start_sec,
                entry.fight_end_sec,
            )
        except Exception as exc:
            logger.warning("Could not resolve BrettZone trim defaults for %s: %s", output_path, exc)
            trim_bounds = None

        # Avoid stale ORM instance updates by writing directly by primary key.
        update_values = {
            "video_path": str(output_path),
            "stage": ProjectStage.TRIM.value,
        }
        if trim_bounds is not None:
            update_values["trim_start"] = trim_bounds[0]
            update_values["trim_end"] = trim_bounds[1]
        update_result = await db.execute(
            update(Project)
            .where(Project.id == project.id)
            .values(**update_values)
        )
        if update_result.rowcount != 1:
            raise RuntimeError(f"Project update failed for id={project.id}: rowcount={update_result.rowcount}")
        await db.commit()
        video_update_applied = True
        refreshed = await db.execute(select(Project).where(Project.id == project.id))
        saved_project = refreshed.scalar_one()

        _start_conversion_background(
            project_id=saved_project.id,
            video_path=output_path,
            project_dir=Path(settings.PROJECTS_ROOT_DIR) / str(saved_project.id),
            output_width=settings.OUTPUT_WIDTH,
            inference_width=settings.INFERENCE_WIDTH,
        )

        return BrettzoneImportResponse(
            project=ProjectResponse.model_validate(saved_project),
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
        if created_project_id is not None and not video_update_applied:
            # Best-effort cleanup for imports that fail before video is attached to project.
            try:
                await db.execute(delete(Project).where(Project.id == created_project_id))
                await db.commit()
            except Exception:
                await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach BrettZone. Please try again or use a direct URL.",
        ) from exc
    except Exception as exc:
        await db.rollback()
        if created_project_id is not None and not video_update_applied:
            # Best-effort cleanup for partial imports.
            try:
                await db.execute(delete(Project).where(Project.id == created_project_id))
                await db.commit()
            except Exception:
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


def _normalized_robot_name(name: str) -> str:
    return " ".join(name.replace("_", " ").split()).strip()


def _download_thumbnail_image(image_url: str) -> np.ndarray | None:
    request = Request(
        url=image_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=20.0) as response:
        data = response.read()
    np_data = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(np_data, cv2.IMREAD_UNCHANGED)
    return image


def _resize_thumbnail(image: np.ndarray, target_size: int = THUMBNAIL_SIZE) -> np.ndarray:
    """Center-crop then resize to a fixed square thumbnail size."""
    height, width = image.shape[:2]
    side = min(height, width)
    top = max(0, (height - side) // 2)
    left = max(0, (width - side) // 2)
    cropped = image[top : top + side, left : left + side]
    if cropped.shape[0] == target_size and cropped.shape[1] == target_size:
        return cropped
    return cv2.resize(cropped, (target_size, target_size), interpolation=cv2.INTER_AREA)


def _extract_foreground_pixels_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    if image.shape[2] == 4:
        rgb = image[:, :, :3]
        alpha = image[:, :, 3]
        opaque_mask = alpha > 10
        if np.any(opaque_mask):
            pixels = rgb[opaque_mask]
        else:
            pixels = rgb.reshape(-1, 3)
    else:
        rgb = image[:, :, :3]
        pixels = rgb.reshape(-1, 3)

    if pixels.size == 0:
        return np.empty((0, 3), dtype=np.uint8)

    height, width = rgb.shape[:2]
    border_pixels = np.concatenate(
        [
            rgb[0, :, :],
            rgb[height - 1, :, :],
            rgb[:, 0, :],
            rgb[:, width - 1, :],
        ],
        axis=0,
    )
    if border_pixels.size == 0:
        return pixels

    bg_color = np.median(border_pixels, axis=0)
    distances = np.linalg.norm(pixels.astype(np.float32) - bg_color.astype(np.float32), axis=1)
    foreground_pixels = pixels[distances > 30.0]
    candidate_pixels = foreground_pixels if foreground_pixels.size != 0 else pixels
    if candidate_pixels.size == 0:
        return candidate_pixels

    # Remove near-neutral background tones (black/white/gray) so color selection
    # focuses on robot highlights/accents.
    hsv = cv2.cvtColor(candidate_pixels.reshape((-1, 1, 3)), cv2.COLOR_BGR2HSV).reshape((-1, 3))
    saturation = hsv[:, 1]
    value = hsv[:, 2]
    colorful_midtones_mask = (saturation >= 35) & (value >= 30) & (value <= 245)
    filtered_pixels = candidate_pixels[colorful_midtones_mask]

    # Keep behavior robust for robots with very little chroma in their thumbnail.
    if filtered_pixels.shape[0] >= 128:
        return filtered_pixels
    return candidate_pixels


def _dominant_color_hex_from_image(image: np.ndarray) -> str:
    foreground_pixels = _extract_foreground_pixels_bgr(image)
    if foreground_pixels.size == 0:
        return "#2563eb"

    sample = foreground_pixels
    max_samples = 20000
    if sample.shape[0] > max_samples:
        indices = np.random.choice(sample.shape[0], max_samples, replace=False)
        sample = sample[indices]

    sample_float = sample.astype(np.float32)
    k = min(6, max(1, sample_float.shape[0]))
    if sample_float.shape[0] < k:
        k = sample_float.shape[0]

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
    _compactness, labels, centers = cv2.kmeans(
        sample_float,
        k,
        None,
        criteria,
        5,
        cv2.KMEANS_PP_CENTERS,
    )
    label_counts = np.bincount(labels.flatten(), minlength=k)
    centers_u8 = np.clip(centers, 0, 255).astype(np.uint8)
    centers_hsv = cv2.cvtColor(centers_u8.reshape((-1, 1, 3)), cv2.COLOR_BGR2HSV).reshape((-1, 3))

    best_index = -1
    best_score = -1.0
    for idx in range(k):
        count = float(label_counts[idx])
        sat = float(centers_hsv[idx][1])
        val = float(centers_hsv[idx][2])

        # Reject likely black/white/gray background clusters.
        if sat < 28 or val < 28 or val > 245:
            continue

        # Favor saturated highlight colors while still considering cluster area.
        score = count * ((sat / 255.0) ** 1.35) * (0.65 + min(val, 220.0) / 255.0)
        if score > best_score:
            best_score = score
            best_index = idx

    if best_index < 0:
        best_index = int(np.argmax(label_counts))

    b, g, r = centers[best_index]
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _save_label_thumbnail_image(label_id: UUID, image: np.ndarray) -> str | None:
    root = Path(settings.PROJECTS_ROOT_DIR)
    thumbs_dir = root / "label_thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    output_path = thumbs_dir / f"{label_id}.jpg"

    resized = _resize_thumbnail(image)
    if resized.ndim == 3 and resized.shape[2] == 4:
        resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2BGR)

    success = cv2.imwrite(str(output_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        return None
    return f"{settings.API_V1_STR}/labels/{label_id}/thumbnail"


async def _ensure_robot_labels_for_project(
    project_id: UUID,
    robot_names: list[str],
    robot_thumbnails: dict[str, str],
    db: AsyncSession,
) -> None:
    deduped_names: list[str] = []
    seen_names: set[str] = set()
    for raw_name in robot_names:
        display_name = raw_name.strip()
        compare_name = _normalized_robot_name(display_name)
        if not compare_name:
            continue
        key = compare_name.casefold()
        if key in seen_names:
            continue
        seen_names.add(key)
        deduped_names.append(display_name)

    logger.info("BrettZone robot labels candidate names: %s", deduped_names)

    thumbnail_by_name: dict[str, str] = {}
    for name, url in robot_thumbnails.items():
        compare_name = _normalized_robot_name(name)
        if compare_name and url:
            thumbnail_by_name.setdefault(compare_name.casefold(), url)

    existing_labels_result = await db.execute(select(Label))
    existing_labels = existing_labels_result.scalars().all()
    label_by_name = {_normalized_robot_name(label.name).casefold(): label for label in existing_labels}

    project_label_ids: list[UUID] = []
    for robot_display_name in deduped_names:
        compare_key = _normalized_robot_name(robot_display_name).casefold()
        existing_label = label_by_name.get(compare_key)
        if existing_label is None:
            thumbnail_url = thumbnail_by_name.get(compare_key)
            dominant_color_hex = "#2563eb"
            thumbnail_image: np.ndarray | None = None
            thumbnail_path: str | None = None
            if thumbnail_url:
                try:
                    thumbnail_image = await asyncio.to_thread(_download_thumbnail_image, thumbnail_url)
                except Exception as exc:
                    logger.warning(
                        "Failed to download robot thumbnail for %s from %s: %s",
                        robot_display_name,
                        thumbnail_url,
                        exc,
                    )
            if thumbnail_image is not None:
                dominant_color_hex = _dominant_color_hex_from_image(thumbnail_image)
                try:
                    # Pre-generate ID so thumbnail path can be set before first DB flush.
                    precreated_label_id = uuid4()
                    thumbnail_path = await asyncio.to_thread(
                        _save_label_thumbnail_image,
                        precreated_label_id,
                        thumbnail_image,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to persist robot thumbnail for %s: %s",
                        robot_display_name,
                        exc,
                    )
                    precreated_label_id = uuid4()
            else:
                precreated_label_id = uuid4()

            existing_label = Label(
                id=precreated_label_id,
                name=robot_display_name,
                color_hex=dominant_color_hex,
                thumbnail_path=thumbnail_path,
            )
            db.add(existing_label)
            await db.flush()
            label_by_name[compare_key] = existing_label
            logger.info("Created label from BrettZone robot name: %s", robot_display_name)
        project_label_ids.append(existing_label.id)

    # Auto-enable any globally configured always-include labels.
    for label in label_by_name.values():
        if label.always_include:
            project_label_ids.append(label.id)

    existing_settings_result = await db.execute(
        select(ProjectLabelSetting).where(ProjectLabelSetting.project_id == project_id)
    )
    existing_settings = existing_settings_result.scalars().all()
    existing_label_ids = {setting.label_id for setting in existing_settings}

    for label_id in project_label_ids:
        if label_id in existing_label_ids:
            continue
        db.add(
            ProjectLabelSetting(
                project_id=project_id,
                label_id=label_id,
                enabled=True,
            )
        )
    logger.info(
        "BrettZone label settings upsert complete for project %s: enabled_label_ids=%s",
        project_id,
        project_label_ids,
    )
