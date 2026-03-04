"""Utilities for parsing mask contour_polygon data in both legacy and new formats."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def parse_contour_polygon(
    contour_polygon: Any,
) -> tuple[list[np.ndarray], np.ndarray | None]:
    """Parse the contour_polygon field from a Mask row.

    Supports two formats:
    - **New** (dict): ``{"contours": [[[x,y], ...], ...], "hierarchy": [[n,p,c,par], ...]}``
    - **Legacy** (list): ``[[x,y], [x,y], ...]``  (single contour, no hierarchy)

    Returns:
        (contours, hierarchy) where each contour is an ``(N, 1, 2)`` int32 array
        and hierarchy is ``(1, M, 4)`` int32 or ``None``.
    """
    if isinstance(contour_polygon, dict):
        raw_contours = contour_polygon.get("contours", [])
        raw_hierarchy = contour_polygon.get("hierarchy")
        contours = [
            np.array(c, dtype=np.int32).reshape(-1, 1, 2) for c in raw_contours if len(c) >= 3
        ]
        hierarchy = (
            np.array([raw_hierarchy], dtype=np.int32) if raw_hierarchy else None
        )
        return contours, hierarchy

    if isinstance(contour_polygon, list) and len(contour_polygon) >= 3:
        contours = [np.array(contour_polygon, dtype=np.int32).reshape(-1, 1, 2)]
        return contours, None

    return [], None


def draw_contours_on_mask(
    mask: np.ndarray,
    contour_polygon: Any,
    value: int,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> None:
    """Draw contours onto a segmentation mask image, preserving holes.

    Args:
        mask: Target single-channel image (modified in-place).
        contour_polygon: The ``contour_polygon`` field from a Mask row.
        value: Pixel value to fill outer contours with.
        scale_x: Horizontal scale factor applied to contour coordinates.
        scale_y: Vertical scale factor applied to contour coordinates.
    """
    contours, hierarchy = parse_contour_polygon(contour_polygon)
    if not contours:
        return

    if scale_x != 1.0 or scale_y != 1.0:
        scaled = []
        for c in contours:
            fc = c.astype(np.float64)
            fc[:, :, 0] *= scale_x
            fc[:, :, 1] *= scale_y
            scaled.append(fc.astype(np.int32))
        contours = scaled

    if hierarchy is not None:
        cv2.drawContours(mask, contours, -1, int(value), cv2.FILLED, hierarchy=hierarchy)
    else:
        cv2.drawContours(mask, contours, -1, int(value), cv2.FILLED)


def contour_bounding_box(
    contour_polygon: Any,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> tuple[float, float, float, float] | None:
    """Compute the axis-aligned bounding box of all contours.

    Returns:
        ``(xmin, ymin, xmax, ymax)`` or ``None`` if contours are empty.
    """
    contours, _ = parse_contour_polygon(contour_polygon)
    if not contours:
        return None

    all_pts = np.concatenate([c.reshape(-1, 2) for c in contours], axis=0).astype(np.float64)
    all_pts[:, 0] *= scale_x
    all_pts[:, 1] *= scale_y

    xmin, ymin = all_pts.min(axis=0)
    xmax, ymax = all_pts.max(axis=0)
    return float(xmin), float(ymin), float(xmax), float(ymax)
