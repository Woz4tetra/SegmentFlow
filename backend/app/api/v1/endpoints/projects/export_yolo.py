"""Export images and labels in YOLO format as a ZIP archive."""

import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

import cv2
from fastapi import Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.trim_utils import get_trim_frame_bounds
from app.models.image import Image
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


@router.get("/projects/{project_id}/export/yolo")
async def export_yolo(
    project_id: UUID,
    skip_n: int = Query(1, ge=1, description="Skip every Nth frame in export"),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Export project images and YOLO labels as a ZIP."""
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
        label_index = {label.id: idx for idx, label in enumerate(labels)}

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

        export_dir = Path(tempfile.mkdtemp(prefix="segmentflow_export_"))
        images_dir = export_dir / "images"
        labels_dir = export_dir / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        data_path = export_dir / "data.yml"
        data_lines = [
            "names:",
            *[f"- {label.name}" for label in labels],
            "colors:",
            *[f"- \"{label.color_hex}\"" for label in labels],
            f"nc: {len(labels)}",
            "test: ../test/images",
            "train: ../train/images",
            "val: ../val/images",
        ]
        data_path.write_text("\n".join(data_lines), encoding="utf-8")

        for idx, image in enumerate(images):
            if skip_n > 1 and idx % skip_n != 0:
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

            out_image_path = images_dir / image_path.name
            shutil.copyfile(image_path, out_image_path)

            label_lines: list[str] = []
            by_label = masks_by_image.get(image.id, {})
            for label_id, mask in by_label.items():
                if label_id not in label_index:
                    continue
                contour = mask.contour_polygon or []
                if not contour:
                    continue
                xs = [pt[0] * scale_x for pt in contour]
                ys = [pt[1] * scale_y for pt in contour]
                xmin, xmax = max(0.0, min(xs)), min(float(width), max(xs))
                ymin, ymax = max(0.0, min(ys)), min(float(height), max(ys))
                if xmax <= xmin or ymax <= ymin:
                    continue
                x_center = (xmin + xmax) / 2.0 / width
                y_center = (ymin + ymax) / 2.0 / height
                box_w = (xmax - xmin) / width
                box_h = (ymax - ymin) / height
                class_id = label_index[label_id]
                label_lines.append(
                    f"{class_id} {x_center:.6f} {y_center:.6f} {box_w:.6f} {box_h:.6f}"
                )

            label_path = labels_dir / f"{image_path.stem}.txt"
            label_path.write_text("\n".join(label_lines), encoding="utf-8")

        zip_path = export_dir / f"{project.name}_export.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for path in export_dir.rglob("*"):
                if path == zip_path:
                    continue
                zipf.write(path, path.relative_to(export_dir))

        return FileResponse(
            str(zip_path),
            media_type="application/zip",
            filename=zip_path.name,
            background=BackgroundTask(_cleanup_export, export_dir),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to export YOLO ZIP: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export YOLO ZIP",
        ) from e
