"""Resize all label thumbnails to a fixed 128x128 JPG format.

Usage:
  PYTHONPATH=. python scripts/resize_label_thumbnails.py
  PYTHONPATH=. python scripts/resize_label_thumbnails.py --dry-run
  PYTHONPATH=. python scripts/resize_label_thumbnails.py --size 128
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.label import Label


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize label thumbnails to fixed-size JPG files.")
    parser.add_argument("--size", type=int, default=128, help="Target thumbnail width/height (default: 128)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files/DB")
    return parser


def _resize_thumbnail_to_square(image: np.ndarray, target_size: int) -> np.ndarray:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    height, width = image.shape[:2]
    side = min(height, width)
    top = max(0, (height - side) // 2)
    left = max(0, (width - side) // 2)
    cropped = image[top : top + side, left : left + side]
    resized = cv2.resize(cropped, (target_size, target_size), interpolation=cv2.INTER_AREA)
    if resized.ndim == 3 and resized.shape[2] == 4:
        resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2BGR)
    if resized.ndim == 2:
        resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
    return resized


def _existing_thumbnail_file(thumbs_dir: Path, label_id: UUID) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = thumbs_dir / f"{label_id}{ext}"
        if candidate.exists():
            return candidate
    return None


async def _run(size: int, dry_run: bool) -> int:
    thumbs_dir = Path(settings.PROJECTS_ROOT_DIR) / "label_thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    normalized_route_template = f"{settings.API_V1_STR}/labels/{{label_id}}/thumbnail"

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Label))
        labels = result.scalars().all()

        resized_count = 0
        removed_legacy_count = 0
        db_updated_count = 0
        db_cleared_count = 0

        for label in labels:
            source_path = _existing_thumbnail_file(thumbs_dir, label.id)
            normalized_route = normalized_route_template.format(label_id=label.id)

            if source_path is None:
                if label.thumbnail_path is not None:
                    db_cleared_count += 1
                    if not dry_run:
                        label.thumbnail_path = None
                continue

            image = cv2.imread(str(source_path), cv2.IMREAD_UNCHANGED)
            if image is None:
                continue
            resized = _resize_thumbnail_to_square(image, target_size=size)
            dest_path = thumbs_dir / f"{label.id}.jpg"

            if not dry_run:
                ok = cv2.imwrite(str(dest_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if not ok:
                    continue
                for ext in (".png", ".jpeg"):
                    legacy_path = thumbs_dir / f"{label.id}{ext}"
                    if legacy_path.exists():
                        legacy_path.unlink()
                        removed_legacy_count += 1
            resized_count += 1

            if label.thumbnail_path != normalized_route:
                db_updated_count += 1
                if not dry_run:
                    label.thumbnail_path = normalized_route

        if not dry_run:
            await db.commit()

    print(f"labels_scanned={len(labels)}")
    print(f"thumbnails_resized={resized_count}")
    print(f"legacy_files_removed={removed_legacy_count}")
    print(f"db_thumbnail_paths_updated={db_updated_count}")
    print(f"db_thumbnail_paths_cleared={db_cleared_count}")
    print(f"dry_run={dry_run}")
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    if args.size <= 0:
        raise SystemExit("--size must be a positive integer")
    return asyncio.run(_run(size=args.size, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
