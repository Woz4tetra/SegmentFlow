"""Tests for mask -> contour conversion and filtering."""

import cv2
import numpy as np

from app.core.contour_utils import (
    draw_contours_on_mask,
    mask_to_contour_data,
    parse_contour_polygon,
)


def _blank(height: int = 200, width: int = 200) -> np.ndarray:
    return np.zeros((height, width), dtype=np.uint8)


def _blob_with_hole_and_speckle() -> np.ndarray:
    """Build a mask with one big blob, a hole inside it, and a 3x3 speckle."""
    mask = _blank()
    mask[20:120, 20:120] = 1  # 100x100 blob
    mask[50:70, 50:70] = 0  # 20x20 hole
    mask[180:183, 180:183] = 1  # 3x3 speckle (area 4 by contourArea)
    return mask


class TestMaskToContourData:
    """Filtering behavior shared by manual labeling and propagation."""

    def test_drops_speckles_and_keeps_hole(self) -> None:
        result = mask_to_contour_data(_blob_with_hole_and_speckle(), min_area=30.0)
        assert result is not None
        data, area = result

        contours = data["contours"]
        hierarchy = data["hierarchy"]
        assert len(contours) == 2, "expected the blob outline plus its hole"
        assert len(hierarchy) == len(contours)

        outers = [i for i, h in enumerate(hierarchy) if h[3] == -1]
        holes = [i for i, h in enumerate(hierarchy) if h[3] != -1]
        assert len(outers) == 1
        assert len(holes) == 1
        assert hierarchy[holes[0]][3] == outers[0]
        assert hierarchy[outers[0]][2] == holes[0]

        # Hole area is subtracted, not added. Contour areas measure the polygon
        # through pixel centers, so they do not equal the raw pixel counts:
        # the outer square traces at 99x99 and the hole ring at 439.
        outer_area = cv2.contourArea(
            np.array(contours[outers[0]], dtype=np.int32).reshape(-1, 1, 2)
        )
        hole_area = cv2.contourArea(np.array(contours[holes[0]], dtype=np.int32).reshape(-1, 1, 2))
        assert outer_area == 99 * 99
        assert area == outer_area - hole_area

        # Sanity check against the true filled-pixel count (100x100 - 20x20).
        assert abs(area - 9600) / 9600 < 0.03

    def test_speckle_survives_when_threshold_is_low(self) -> None:
        result = mask_to_contour_data(_blob_with_hole_and_speckle(), min_area=1.0)
        assert result is not None
        data, _area = result
        outers = [h for h in data["hierarchy"] if h[3] == -1]
        assert len(outers) == 2, "speckle should be kept when it clears min_area"

    def test_preserve_holes_false_drops_children(self) -> None:
        result = mask_to_contour_data(
            _blob_with_hole_and_speckle(), min_area=30.0, preserve_holes=False
        )
        assert result is not None
        data, area = result
        assert len(data["contours"]) == 1
        assert data["hierarchy"] == [[-1, -1, -1, -1]]
        assert area == 99 * 99, "hole area is not subtracted when holes are dropped"

    def test_keeps_only_the_largest_contours(self) -> None:
        mask = _blank(400, 400)
        mask[10:110, 10:110] = 1  # largest
        mask[10:60, 200:250] = 1  # medium
        mask[300:320, 300:320] = 1  # smallest
        result = mask_to_contour_data(mask, min_area=30.0, max_contours=2)
        assert result is not None
        data, _area = result
        assert len(data["contours"]) == 2

        areas = sorted(
            cv2.contourArea(np.array(c, dtype=np.int32).reshape(-1, 1, 2)) for c in data["contours"]
        )
        assert areas == [49 * 49, 99 * 99], "the smallest blob should be dropped"

    def test_sorted_by_area_descending(self) -> None:
        mask = _blank(400, 400)
        mask[300:320, 300:320] = 1  # smallest, but found first by scan order
        mask[10:110, 10:110] = 1  # largest
        result = mask_to_contour_data(mask, min_area=30.0)
        assert result is not None
        data, _area = result
        first = cv2.contourArea(np.array(data["contours"][0], dtype=np.int32).reshape(-1, 1, 2))
        second = cv2.contourArea(np.array(data["contours"][1], dtype=np.int32).reshape(-1, 1, 2))
        assert first > second

    def test_returns_none_for_empty_mask(self) -> None:
        assert mask_to_contour_data(_blank()) is None

    def test_returns_none_when_everything_is_below_threshold(self) -> None:
        mask = _blank()
        mask[50:53, 50:53] = 1
        assert mask_to_contour_data(mask, min_area=30.0) is None

    def test_returns_none_for_non_2d_mask(self) -> None:
        assert mask_to_contour_data(np.zeros((2, 10, 10), dtype=np.uint8)) is None

    def test_accepts_leading_singleton_dims(self) -> None:
        mask = _blob_with_hole_and_speckle()
        squeezed = mask_to_contour_data(mask, min_area=30.0)
        expanded = mask_to_contour_data(mask[np.newaxis, ...], min_area=30.0)
        assert squeezed is not None
        assert expanded is not None
        assert expanded[0] == squeezed[0]
        assert expanded[1] == squeezed[1]

    def test_accepts_bool_and_float_masks(self) -> None:
        mask = _blob_with_hole_and_speckle()
        as_uint8 = mask_to_contour_data(mask, min_area=30.0)
        as_bool = mask_to_contour_data(mask.astype(bool), min_area=30.0)
        as_float = mask_to_contour_data(mask.astype(np.float32), min_area=30.0)
        assert as_uint8 is not None
        assert as_bool is not None
        assert as_float is not None
        assert as_bool[0] == as_uint8[0]
        assert as_float[0] == as_uint8[0]


class TestContourRoundTrip:
    """The emitted payload must survive parsing and redrawing."""

    def test_hierarchy_round_trips_through_draw(self) -> None:
        result = mask_to_contour_data(_blob_with_hole_and_speckle(), min_area=30.0)
        assert result is not None
        data, _area = result

        contours, hierarchy = parse_contour_polygon(data)
        assert len(contours) == 2
        assert hierarchy is not None
        assert hierarchy.shape == (1, 2, 4)

        redrawn = _blank()
        draw_contours_on_mask(redrawn, data, value=255)
        assert redrawn[70, 70] == 255, "blob interior should be filled"
        assert redrawn[60, 60] == 0, "hole should stay empty"
        assert redrawn[181, 181] == 0, "speckle should not be drawn"
