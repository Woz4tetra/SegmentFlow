"""Utilities for the project-wide crop rectangle.

The crop is stored on the project as four normalized floats (0-1) relative to the source video
dimensions. Normalized coordinates let the same rectangle apply to both the output and inference
frame resolutions, which are rendered at different widths.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.models.project import Project

# Minimum crop size in source pixels, enforced by both the API and the frontend selector.
MIN_CROP_PIXELS = 16


@dataclass(frozen=True)
class CropRect:
    """Normalized crop rectangle.

    Attributes:
        x: Left edge as a fraction of the source width
        y: Top edge as a fraction of the source height
        width: Rectangle width as a fraction of the source width
        height: Rectangle height as a fraction of the source height
    """

    x: float
    y: float
    width: float
    height: float

    def is_full_frame(self) -> bool:
        """Return True when the rectangle covers the whole frame."""
        return (
            self.x <= 0.0
            and self.y <= 0.0
            and self.width >= 1.0
            and self.height >= 1.0
        )

    def to_pixels(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        """Convert to an inclusive-exclusive pixel box clamped to the frame.

        Args:
            frame_width: Width of the frame in pixels
            frame_height: Height of the frame in pixels

        Returns:
            tuple: (x0, y0, x1, y1) with x1 > x0 and y1 > y0
        """
        x0 = min(max(round(self.x * frame_width), 0), max(frame_width - 1, 0))
        y0 = min(max(round(self.y * frame_height), 0), max(frame_height - 1, 0))
        x1 = min(max(round((self.x + self.width) * frame_width), x0 + 1), frame_width)
        y1 = min(max(round((self.y + self.height) * frame_height), y0 + 1), frame_height)
        return x0, y0, x1, y1


def get_project_crop(project: Project) -> CropRect | None:
    """Return the project's crop rectangle, or None when the project is uncropped.

    Args:
        project: Project to read the crop columns from

    Returns:
        CropRect | None: The stored rectangle, or None if any column is unset
    """
    values = (project.crop_x, project.crop_y, project.crop_width, project.crop_height)
    if any(value is None for value in values):
        return None
    x, y, width, height = (float(value) for value in values)  # type: ignore[arg-type]
    if width <= 0.0 or height <= 0.0:
        return None
    return CropRect(x=x, y=y, width=width, height=height)


def crop_frame(frame: np.ndarray, crop: CropRect | None) -> np.ndarray:
    """Crop a frame to the given rectangle.

    Args:
        frame: Frame as a HxWxC array
        crop: Normalized rectangle, or None to leave the frame untouched

    Returns:
        np.ndarray: The cropped frame, or the original frame when crop is None
    """
    if crop is None or crop.is_full_frame():
        return frame
    frame_height, frame_width = frame.shape[0:2]
    if frame_width <= 0 or frame_height <= 0:
        return frame
    x0, y0, x1, y1 = crop.to_pixels(frame_width, frame_height)
    return frame[y0:y1, x0:x1]
