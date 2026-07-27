"""Utilities for building and parsing mask contour_polygon data.

Covers both the legacy (flat list) and new (dict with hierarchy) formats.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _as_binary_2d(mask: np.ndarray) -> np.ndarray | None:
    """Squeeze a mask to a contiguous 2D uint8 array, or return None if it is not 2D."""
    mask_2d = np.squeeze(mask)
    if mask_2d.ndim != 2:
        logger.warning(f"Unexpected mask shape after squeeze: {mask_2d.shape}, expected 2D")
        return None

    if mask_2d.dtype == bool:
        mask_uint8 = mask_2d.astype(np.uint8) * 255
    elif mask_2d.dtype != np.uint8:
        mask_uint8 = (mask_2d * 255).astype(np.uint8)
    else:
        mask_uint8 = mask_2d

    # OpenCV requires a contiguous buffer
    return np.ascontiguousarray(mask_uint8)


def _append_holes(
    parent_idx: int,
    outer_slot: int,
    contours: Any,
    flat: np.ndarray,
    min_area: float,
    contour_payload: list[Any],
    hierarchy_payload: list[list[int]],
) -> float:
    """Append an outer contour's children as holes and return their total area.

    Both payload lists are appended to in place. Holes below ``min_area`` are
    skipped so pinhole speckles inside a blob get dropped too.
    """
    hole_area_total = 0.0
    prev_hole = -1
    child = int(flat[parent_idx][2])

    while child != -1:
        hole_area = float(cv2.contourArea(contours[child]))
        if hole_area >= min_area:
            hole_slot = len(contour_payload)
            contour_payload.append(contours[child].reshape(-1, 2).tolist())
            hierarchy_payload.append([-1, prev_hole, -1, outer_slot])
            if prev_hole == -1:
                hierarchy_payload[outer_slot][2] = hole_slot
            else:
                hierarchy_payload[prev_hole][0] = hole_slot
            prev_hole = hole_slot
            hole_area_total += hole_area
        child = int(flat[child][0])

    return hole_area_total


def mask_to_contour_data(
    mask: np.ndarray,
    min_area: float | None = None,
    max_contours: int | None = None,
    preserve_holes: bool = True,
) -> tuple[dict, float] | None:
    """Convert a binary mask into filtered contour data with hierarchy.

    Small speckles are dropped and only the largest outer contours are kept, so
    manually labeled and propagated frames use identical filtering.

    Args:
        mask: Binary mask (2D, or with leading singleton dims), bool or uint8.
        min_area: Area floor in pixels. Defaults to ``settings.MIN_CONTOUR_AREA_PX``.
        max_contours: Max outer contours to keep, largest first. Defaults to
            ``settings.MAX_PROPAGATION_CONTOURS``.
        preserve_holes: Keep child contours of kept outer contours as holes.

    Returns:
        ``({"contours": [...], "hierarchy": [...]}, area)``, or ``None`` if
        nothing survived filtering. Hierarchy entries are OpenCV-style
        ``[next, prev, first_child, parent]`` indices into ``contours``.
    """
    mask_uint8 = _as_binary_2d(mask)
    if mask_uint8 is None:
        return None

    contours, hierarchy = cv2.findContours(mask_uint8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or hierarchy is None:
        return None

    if min_area is None:
        min_area = float(settings.MIN_CONTOUR_AREA_PX)
    if max_contours is None:
        max_contours = int(settings.MAX_PROPAGATION_CONTOURS)
    max_contours = max(1, max_contours)

    flat = hierarchy[0]  # [next, prev, first_child, parent] per contour

    outers = [
        (idx, float(cv2.contourArea(contours[idx])))
        for idx in range(len(contours))
        if flat[idx][3] == -1
    ]
    outers = [item for item in outers if item[1] >= min_area]
    if not outers:
        return None

    outers.sort(key=lambda item: item[1], reverse=True)
    outers = outers[:max_contours]

    contour_payload: list[Any] = []
    hierarchy_payload: list[list[int]] = []
    total_area = 0.0
    prev_outer = -1

    for parent_idx, outer_area in outers:
        outer_slot = len(contour_payload)
        contour_payload.append(contours[parent_idx].reshape(-1, 2).tolist())
        hierarchy_payload.append([-1, prev_outer, -1, -1])
        if prev_outer != -1:
            hierarchy_payload[prev_outer][0] = outer_slot
        prev_outer = outer_slot
        total_area += outer_area

        if preserve_holes:
            total_area -= _append_holes(
                parent_idx,
                outer_slot,
                contours,
                flat,
                min_area,
                contour_payload,
                hierarchy_payload,
            )

    return {"contours": contour_payload, "hierarchy": hierarchy_payload}, abs(total_area)


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
        hierarchy = np.array([raw_hierarchy], dtype=np.int32) if raw_hierarchy else None
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
