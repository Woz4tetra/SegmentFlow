"""Tests for the crop rectangle utilities."""

import numpy as np

from app.core.crop_utils import CropRect, crop_frame, get_project_crop
from app.models.project import Project


class TestCropRect:
    """Tests for the CropRect dataclass."""

    def test_is_full_frame(self) -> None:
        assert CropRect(x=0.0, y=0.0, width=1.0, height=1.0).is_full_frame()
        assert not CropRect(x=0.0, y=0.0, width=0.5, height=1.0).is_full_frame()

    def test_to_pixels_rounds_and_clamps(self) -> None:
        crop = CropRect(x=0.25, y=0.5, width=0.5, height=0.5)
        assert crop.to_pixels(640, 480) == (160, 240, 480, 480)

    def test_to_pixels_never_returns_empty_box(self) -> None:
        crop = CropRect(x=0.999, y=0.999, width=0.001, height=0.001)
        x0, y0, x1, y1 = crop.to_pixels(100, 100)
        assert x1 > x0
        assert y1 > y0


class TestGetProjectCrop:
    """Tests for reading a crop off a project."""

    def test_returns_none_when_unset(self) -> None:
        assert get_project_crop(Project(name="p")) is None

    def test_returns_none_when_partially_set(self) -> None:
        project = Project(name="p", crop_x=0.1, crop_y=0.1, crop_width=0.5)
        assert get_project_crop(project) is None

    def test_returns_rect_when_set(self) -> None:
        project = Project(
            name="p",
            crop_x=0.1,
            crop_y=0.2,
            crop_width=0.5,
            crop_height=0.6,
        )
        assert get_project_crop(project) == CropRect(x=0.1, y=0.2, width=0.5, height=0.6)

    def test_returns_none_for_degenerate_rect(self) -> None:
        project = Project(name="p", crop_x=0.0, crop_y=0.0, crop_width=0.0, crop_height=0.5)
        assert get_project_crop(project) is None


class TestCropFrame:
    """Tests for applying a crop to a frame."""

    def test_none_returns_original_object(self) -> None:
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        assert crop_frame(frame, None) is frame

    def test_full_frame_returns_original_object(self) -> None:
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        crop = CropRect(x=0.0, y=0.0, width=1.0, height=1.0)
        assert crop_frame(frame, crop) is frame

    def test_crops_requested_region(self) -> None:
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        frame[0:50, 0:100] = 255  # top-left quadrant
        cropped = crop_frame(frame, CropRect(x=0.0, y=0.0, width=0.5, height=0.5))
        assert cropped.shape[0:2] == (50, 100)
        assert int(cropped.min()) == 255

    def test_crop_beyond_bounds_is_clamped(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cropped = crop_frame(frame, CropRect(x=0.9, y=0.9, width=0.5, height=0.5))
        assert cropped.shape[0] <= 100
        assert cropped.shape[1] <= 100
        assert cropped.size > 0
