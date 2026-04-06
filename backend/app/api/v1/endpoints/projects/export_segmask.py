"""Export images and semantic segmentation masks as a ZIP archive."""

import asyncio
import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
from fastapi import Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.config import settings
from app.core.contour_utils import draw_contours_on_mask
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image, ValidationStatus
from app.models.label import Label
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


def _cleanup_export(path: Path) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        logger.warning("Failed to cleanup export directory: %s", path)


def _build_segmask_zip(
    project_name: str,
    images: list[Image],
    labels: list[Label],
    label_index: dict[UUID, int],
    masks_by_image: dict[UUID, dict[UUID, Mask]],
    skip_n: int,
) -> tuple[Path, Path]:
    """Build segmentation mask export zip on a worker thread."""
    export_dir = Path(tempfile.mkdtemp(prefix="segmentflow_segmask_"))
    out_dir = export_dir / "segmask"
    out_dir.mkdir(parents=True, exist_ok=True)

    classes_path = out_dir / "classes.txt"
    class_lines = [f"{idx + 1}: {label.name}" for idx, label in enumerate(labels)]
    classes_path.write_text("\n".join(class_lines), encoding="utf-8")

    for idx, image in enumerate(images):
        if skip_n > 1 and idx % skip_n != 0:
            continue
        if image.validation != ValidationStatus.PASSED.value and not image.manually_labeled:
            continue
        image_rel = image.output_path or image.inference_path
        if not image_rel:
            continue

        image_path = Path(settings.PROJECTS_ROOT_DIR) / image_rel
        if not image_path.exists():
            logger.warning("Missing image file for export: %s", image_path)
            continue

        img = cv2.imread(str(image_path))
        if img is None:
            logger.warning("Failed to read image for export: %s", image_path)
            continue
        height, width = img.shape[:2]
        if width == 0 or height == 0:
            continue

        infer_width = width
        infer_height = height
        if image.output_path and image.inference_path:
            infer_path = Path(settings.PROJECTS_ROOT_DIR) / image.inference_path
            if infer_path.exists():
                infer_img = cv2.imread(str(infer_path))
                if infer_img is None:
                    logger.warning("Failed to read inference image: %s", infer_path)
                else:
                    infer_height, infer_width = infer_img.shape[:2]
        scale_x = width / infer_width if infer_width else 1.0
        scale_y = height / infer_height if infer_height else 1.0

        stem = image_path.stem
        rgb_path = out_dir / f"{stem}.jpg"
        cv2.imwrite(str(rgb_path), img, [cv2.IMWRITE_JPEG_QUALITY, 95])

        seg_mask = np.zeros((height, width), dtype=np.uint8)
        by_label = masks_by_image.get(image.id, {})

        sorted_labels = sorted(by_label.items(), key=lambda item: label_index.get(item[0], 0))
        for label_id, mask in sorted_labels:
            pixel_val = label_index.get(label_id)
            if pixel_val is None:
                continue
            draw_contours_on_mask(
                seg_mask,
                mask.contour_polygon,
                value=pixel_val,
                scale_x=scale_x,
                scale_y=scale_y,
            )

        mask_path = out_dir / f"{stem}_mask.png"
        cv2.imwrite(str(mask_path), seg_mask)

    zip_path = export_dir / f"{project_name}_segmask.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in out_dir.rglob("*"):
            zipf.write(path, path.relative_to(export_dir))
    return zip_path, export_dir


@router.get("/projects/{project_id}/export/segmask")
async def export_segmask(
    project_id: UUID,
    skip_n: int = Query(1, ge=1, description="Skip every Nth frame in export"),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Export project images (JPG) and semantic segmentation masks (PNG) as a ZIP.

    Each label gets a pixel value equal to its 1-based index (sorted by name).
    Higher-indexed labels are painted last and take priority in overlapping regions.
    """
    try:
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        bounds = get_trim_frame_bounds(project)
        images_query = select(Image).where(Image.project_id == project_id)
        if bounds:
            start_frame, end_frame = bounds
            images_query = images_query.where(
                Image.frame_number >= start_frame,
                Image.frame_number <= end_frame,
            )
        images_result = await db.execute(images_query.order_by(Image.frame_number))
        images = list(images_result.scalars().all())
        if not images:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No images available for export in the current trim range",
            )

        labels_result = await db.execute(select(Label).order_by(Label.name))
        labels = list(labels_result.scalars().all())
        label_index = {label.id: idx + 1 for idx, label in enumerate(labels)}

        image_ids = [img.id for img in images]
        masks_result = await db.execute(
            select(Mask).where(Mask.image_id.in_(image_ids))
        )
        masks = list(masks_result.scalars().all())

        masks_by_image: dict[UUID, dict[UUID, Mask]] = {}
        for mask in masks:
            by_label = masks_by_image.setdefault(mask.image_id, {})
            existing = by_label.get(mask.label_id)
            if not existing or mask.area > existing.area:
                by_label[mask.label_id] = mask

        zip_path, export_dir = await asyncio.to_thread(
            _build_segmask_zip,
            project.name,
            images,
            labels,
            label_index,
            masks_by_image,
            skip_n,
        )

        return FileResponse(
            str(zip_path),
            media_type="application/zip",
            filename=zip_path.name,
            background=BackgroundTask(_cleanup_export, export_dir),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to export segmentation mask ZIP: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export segmentation mask ZIP",
        ) from e
