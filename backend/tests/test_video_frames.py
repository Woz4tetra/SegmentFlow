"""Tests for video frame utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from app.core.crop_utils import CropRect
from app.core.video_frames import (
    VideoInfo,
    _build_sampled_frame_indices,
    _open_capture,
    _save_single_frame,
    convert_video_to_jpegs,
    generate_thumbnail,
    get_video_info,
    read_frame_at_index,
    resize_to_width,
)


@pytest.fixture
def mock_video_path(tmp_path: Path) -> Path:
    """Create a mock video file path.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path: Path to mock video file
    """
    video_path = tmp_path / "test_video.mp4"
    video_path.touch()
    return video_path


@pytest.fixture
def mock_image_path(tmp_path: Path) -> Path:
    """Create a mock image file with actual content.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path: Path to mock image file
    """
    image_path = tmp_path / "test_image.jpg"
    # Create a simple test image (100x100 pixels, blue)
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [255, 0, 0]  # Blue in BGR
    cv2.imwrite(str(image_path), img)
    return image_path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create output directory.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path: Output directory path
    """
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    return out_dir


@pytest.fixture
def inference_dir(tmp_path: Path) -> Path:
    """Create inference directory.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path: Inference directory path
    """
    inf_dir = tmp_path / "inference"
    inf_dir.mkdir()
    return inf_dir


class TestOpenCapture:
    """Tests for _open_capture function."""

    def test_open_capture_success(self, mock_video_path: Path) -> None:
        """Test successful video capture opening.

        Args:
            mock_video_path: Mock video file path
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 100,
            cv2.CAP_PROP_FRAME_WIDTH: 1920,
            cv2.CAP_PROP_FRAME_HEIGHT: 1080,
        }.get(prop, 0)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            cap, info = _open_capture(mock_video_path)

            assert cap == mock_cap
            assert info.path == mock_video_path
            assert info.fps == 30.0
            assert info.frame_count == 100
            assert info.width == 1920
            assert info.height == 1080

    def test_open_capture_failure(self, mock_video_path: Path) -> None:
        """Test failure to open video capture.

        Args:
            mock_video_path: Mock video file path
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = False

        with (
            patch("cv2.VideoCapture", return_value=mock_cap),
            pytest.raises(RuntimeError, match="Failed to open video"),
        ):
            _open_capture(mock_video_path)

    def test_open_capture_with_missing_properties(self, mock_video_path: Path) -> None:
        """Test opening video with missing or zero properties.

        Args:
            mock_video_path: Mock video file path
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 0  # Return 0 or None for all properties

        with patch("cv2.VideoCapture", return_value=mock_cap):
            _cap, info = _open_capture(mock_video_path)

            # Should use default fps of 30.0 when property is 0 or None
            assert info.fps == 30.0
            assert info.frame_count == 0
            assert info.width == 0
            assert info.height == 0


class TestGetVideoInfo:
    """Tests for get_video_info function."""

    def test_get_video_info(self, mock_video_path: Path) -> None:
        """Test getting video information.

        Args:
            mock_video_path: Mock video file path
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 25.0,
            cv2.CAP_PROP_FRAME_COUNT: 250,
            cv2.CAP_PROP_FRAME_WIDTH: 1280,
            cv2.CAP_PROP_FRAME_HEIGHT: 720,
        }.get(prop, 0)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            info = get_video_info(mock_video_path)

            assert info.path == mock_video_path
            assert info.fps == 25.0
            assert info.frame_count == 250
            assert info.width == 1280
            assert info.height == 720
            # Verify capture was released
            mock_cap.release.assert_called_once()


class TestSaveSingleFrame:
    """Tests for _save_single_frame function."""

    def test_save_single_frame(self, tmp_path: Path) -> None:
        """Test saving a single frame.

        Args:
            tmp_path: pytest temporary path fixture
        """
        # Create a test frame (640x480 pixels)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = [0, 255, 0]  # Green

        output_path = tmp_path / "output" / "frame.jpg"
        output_width = 320

        _save_single_frame(frame, output_path, output_width)

        # Verify file was created
        assert output_path.exists()

        # Verify resizing was correct
        saved_img = cv2.imread(str(output_path))
        assert saved_img is not None
        assert saved_img.shape[1] == output_width  # Width
        assert saved_img.shape[0] == 240  # Height (proportionally resized)

    def test_save_single_frame_creates_directory(self, tmp_path: Path) -> None:
        """Test that parent directories are created.

        Args:
            tmp_path: pytest temporary path fixture
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        output_path = tmp_path / "deep" / "nested" / "dirs" / "frame.jpg"

        _save_single_frame(frame, output_path, 50)

        assert output_path.exists()
        assert output_path.parent.exists()


class TestConvertVideoToJpegs:
    """Tests for convert_video_to_jpegs function."""

    def test_convert_video_to_jpegs_success(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test successful video conversion.

        Args:
            mock_video_path: Mock video file path
            output_dir: Output directory
            inference_dir: Inference directory
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 3,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)

        # Mock frame reading
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)

        mock_progress = MagicMock()

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            result = convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
                progress_callback=mock_progress,
            )

            # Should return False (no error)
            assert result is False
            # Should have called imwrite for 3 frames * 2 outputs = 6 times
            assert mock_imwrite.call_count == 6
            # Progress callback should be called
            assert mock_progress.call_count > 0
            # Capture should be released
            mock_cap.release.assert_called_once()

    def test_convert_video_to_jpegs_respects_desired_fps(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test conversion downsampling based on desired fps."""
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 10,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)

        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            result = convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
                desired_fps=10.0,
            )

            assert result is False
            # 30fps source -> 10fps desired over 10 frames => 4 sampled frames, 2 writes each.
            assert mock_imwrite.call_count == 8

    def test_convert_video_to_jpegs_read_failure(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test video conversion with frame read failure.

        Args:
            mock_video_path: Mock video file path
            output_dir: Output directory
            inference_dir: Inference directory
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 5,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)

        # Mock frame reading to fail on second frame
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.side_effect = [
            (True, test_frame),
            (False, None),  # Fail on second read
        ]

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            result = convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
            )

            # Should return False but the capture ended early
            assert result is False
            # Capture should be released
            mock_cap.release.assert_called_once()

    def test_convert_video_to_jpegs_with_exception(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test video conversion with exception during processing.

        Args:
            mock_video_path: Mock video file path
            output_dir: Output directory
            inference_dir: Inference directory
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 2,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)

        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)

        with (
            patch("cv2.VideoCapture", return_value=mock_cap),
            patch(
                "app.core.video_frames._save_single_frame",
                side_effect=Exception("Save failed"),
            ),
        ):
            result = convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
            )

            # Should return True (error occurred)
            assert result is True
            # Capture should be released even with exception
            mock_cap.release.assert_called_once()

    def test_convert_video_to_jpegs_without_progress_callback(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test video conversion without progress callback.

        Args:
            mock_video_path: Mock video file path
            output_dir: Output directory
            inference_dir: Inference directory
        """
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 2,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)

        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            result = convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
                progress_callback=None,  # No callback
            )

            # Should succeed without callback
            assert result is False
            mock_cap.release.assert_called_once()


class TestGenerateThumbnail:
    """Tests for generate_thumbnail function."""

    def test_generate_thumbnail_success(self, mock_image_path: Path, tmp_path: Path) -> None:
        """Test successful thumbnail generation.

        Args:
            mock_image_path: Mock image file path
            tmp_path: pytest temporary path fixture
        """
        output_path = tmp_path / "thumbnails" / "thumb.jpg"

        result = generate_thumbnail(mock_image_path, output_path, max_width=50, quality=85)

        assert result == output_path
        assert output_path.exists()

        # Verify thumbnail dimensions
        thumb = cv2.imread(str(output_path))
        assert thumb is not None
        assert thumb.shape[1] == 50  # Width should be 50
        assert thumb.shape[0] == 50  # Height should be proportional (100x100 -> 50x50)

    def test_generate_thumbnail_no_resize_needed(
        self, mock_image_path: Path, tmp_path: Path
    ) -> None:
        """Test thumbnail generation when image is smaller than max_width.

        Args:
            mock_image_path: Mock image file path
            tmp_path: pytest temporary path fixture
        """
        output_path = tmp_path / "thumb_no_resize.jpg"

        # max_width larger than actual image (100px)
        result = generate_thumbnail(mock_image_path, output_path, max_width=200, quality=90)

        assert result == output_path
        assert output_path.exists()

        # Original size should be preserved
        thumb = cv2.imread(str(output_path))
        assert thumb is not None
        assert thumb.shape[1] == 100  # Original width
        assert thumb.shape[0] == 100  # Original height

    def test_generate_thumbnail_invalid_image(self, tmp_path: Path) -> None:
        """Test thumbnail generation with invalid image.

        Args:
            tmp_path: pytest temporary path fixture
        """
        invalid_path = tmp_path / "invalid.jpg"
        invalid_path.write_text("not an image")

        output_path = tmp_path / "thumb.jpg"

        with pytest.raises(RuntimeError, match="Failed to read image"):
            generate_thumbnail(invalid_path, output_path)

    def test_generate_thumbnail_encode_failure(self, mock_image_path: Path, tmp_path: Path) -> None:
        """Test thumbnail generation with encoding failure.

        Args:
            mock_image_path: Mock image file path
            tmp_path: pytest temporary path fixture
        """
        output_path = tmp_path / "thumb.jpg"

        with (
            patch("cv2.imencode", return_value=(False, None)),
            pytest.raises(RuntimeError, match="Failed to encode thumbnail"),
        ):
            generate_thumbnail(mock_image_path, output_path)

    def test_generate_thumbnail_creates_parent_dirs(
        self, mock_image_path: Path, tmp_path: Path
    ) -> None:
        """Test that parent directories are created for output.

        Args:
            mock_image_path: Mock image file path
            tmp_path: pytest temporary path fixture
        """
        output_path = tmp_path / "deep" / "nested" / "path" / "thumb.jpg"

        result = generate_thumbnail(mock_image_path, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.parent.exists()

    def test_generate_thumbnail_custom_quality(self, mock_image_path: Path, tmp_path: Path) -> None:
        """Test thumbnail generation with different quality settings.

        Args:
            mock_image_path: Mock image file path
            tmp_path: pytest temporary path fixture
        """
        output_low = tmp_path / "thumb_low.jpg"
        output_high = tmp_path / "thumb_high.jpg"

        generate_thumbnail(mock_image_path, output_low, max_width=50, quality=10)
        generate_thumbnail(mock_image_path, output_high, max_width=50, quality=100)

        # Both should exist
        assert output_low.exists()
        assert output_high.exists()

        # High quality should generally be larger file size
        # (though not guaranteed for all images)
        assert output_low.stat().st_size > 0
        assert output_high.stat().st_size > 0


class TestVideoInfo:
    """Tests for VideoInfo dataclass."""

    def test_video_info_creation(self, tmp_path: Path) -> None:
        """Test VideoInfo dataclass creation.

        Args:
            tmp_path: pytest temporary path fixture
        """
        video_path = tmp_path / "test.mp4"
        info = VideoInfo(
            path=video_path,
            fps=29.97,
            frame_count=1000,
            width=1920,
            height=1080,
        )

        assert info.path == video_path
        assert info.fps == 29.97
        assert info.frame_count == 1000
        assert info.width == 1920
        assert info.height == 1080


class TestBuildSampledFrameIndices:
    """Tests for frame sampling helper."""

    def test_build_sampled_frame_indices_returns_all_when_unset(self) -> None:
        assert _build_sampled_frame_indices(5, 30.0, None) == [0, 1, 2, 3, 4]

    def test_build_sampled_frame_indices_downsamples(self) -> None:
        assert _build_sampled_frame_indices(10, 30.0, 10.0) == [0, 3, 6, 9]


class TestReadFrameAtIndex:
    """Tests for decoding a single frame from the source video."""

    def test_read_frame_at_index_seeks_and_returns_frame(self, mock_video_path: Path) -> None:
        """Test that the capture is seeked to the requested frame and released."""
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 100,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, test_frame)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            frame = read_frame_at_index(mock_video_path, 42)

        assert frame is not None
        mock_cap.set.assert_called_once_with(cv2.CAP_PROP_POS_FRAMES, 42)
        mock_cap.release.assert_called_once()

    def test_read_frame_at_index_clamps_to_last_frame(self, mock_video_path: Path) -> None:
        """Test that an out-of-range index is clamped to the final frame."""
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 10,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480,
        }.get(prop, 0)
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

        with patch("cv2.VideoCapture", return_value=mock_cap):
            read_frame_at_index(mock_video_path, 999)

        mock_cap.set.assert_called_once_with(cv2.CAP_PROP_POS_FRAMES, 9)

    def test_read_frame_at_index_returns_none_on_failure(self, mock_video_path: Path) -> None:
        """Test that a failed read returns None instead of raising."""
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 10
        mock_cap.read.return_value = (False, None)

        with patch("cv2.VideoCapture", return_value=mock_cap):
            assert read_frame_at_index(mock_video_path, 0) is None

        mock_cap.release.assert_called_once()


class TestResizeToWidth:
    """Tests for the aspect-preserving resize helper."""

    def test_resize_to_width_preserves_aspect_ratio(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        resized = resize_to_width(frame, 320)
        assert resized.shape[1] == 320
        assert resized.shape[0] == 240

    def test_resize_to_width_noop_when_already_target(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert resize_to_width(frame, 640) is frame


class TestConvertVideoToJpegsWithCrop:
    """Tests for cropping applied during conversion."""

    def _mock_capture(self, frame: np.ndarray, frame_count: int = 1) -> MagicMock:
        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: frame_count,
            cv2.CAP_PROP_FRAME_WIDTH: frame.shape[1],
            cv2.CAP_PROP_FRAME_HEIGHT: frame.shape[0],
        }.get(prop, 0)
        mock_cap.read.return_value = (True, frame)
        return mock_cap

    def test_crop_changes_saved_aspect_ratio(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test that a half-height crop halves the saved frame height."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap = self._mock_capture(frame)

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            result = convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
                crop=CropRect(x=0.0, y=0.0, width=1.0, height=0.5),
            )

        assert result is False
        assert mock_imwrite.call_count == 2
        # Source 640x240 crop resized to width 320 keeps the 8:3 aspect ratio
        output_image = mock_imwrite.call_args_list[0][0][1]
        assert output_image.shape[1] == 320
        assert output_image.shape[0] == 120

    def test_crop_selects_requested_region(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test that only the pixels inside the crop rectangle are kept."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[50:100, 50:100] = 255  # bottom-right quadrant is white
        mock_cap = self._mock_capture(frame)

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=50,
                inference_width=50,
                crop=CropRect(x=0.5, y=0.5, width=0.5, height=0.5),
            )

        saved = mock_imwrite.call_args_list[0][0][1]
        assert saved.shape[0:2] == (50, 50)
        assert int(saved.min()) == 255

    def test_no_crop_keeps_full_frame(
        self,
        mock_video_path: Path,
        output_dir: Path,
        inference_dir: Path,
    ) -> None:
        """Test that crop=None leaves the frame untouched."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap = self._mock_capture(frame)

        with patch("cv2.VideoCapture", return_value=mock_cap), patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = True
            convert_video_to_jpegs(
                mock_video_path,
                output_dir,
                inference_dir,
                output_width=320,
                inference_width=640,
                crop=None,
            )

        output_image = mock_imwrite.call_args_list[0][0][1]
        assert output_image.shape[1] == 320
        assert output_image.shape[0] == 240
