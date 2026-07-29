"""Tests for the OpenCV-decodability fallback."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from app.core.video_transcode import (
    ensure_opencv_readable,
    is_opencv_readable,
    transcode_to_h264,
)

MODULE = "app.core.video_transcode"


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    """Create a placeholder video file path."""
    path = tmp_path / "original.mp4"
    path.touch()
    return path


def _capture(opened: bool, frame: np.ndarray | None) -> MagicMock:
    """Build a mock VideoCapture that opens and reads as specified."""
    cap = MagicMock(spec=cv2.VideoCapture)
    cap.isOpened.return_value = opened
    cap.read.return_value = (frame is not None, frame)
    return cap


class TestIsOpenCVReadable:
    """Tests for is_opencv_readable."""

    def test_true_when_a_frame_decodes(self, video_path: Path) -> None:
        """A capture that yields a frame is readable."""
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        with patch("cv2.VideoCapture", return_value=_capture(True, frame)):
            assert is_opencv_readable(video_path) is True

    def test_false_when_open_succeeds_but_read_fails(self, video_path: Path) -> None:
        """Codecs OpenCV cannot decode open cleanly and then fail every read."""
        cap = _capture(True, None)
        with patch("cv2.VideoCapture", return_value=cap):
            assert is_opencv_readable(video_path) is False
        cap.release.assert_called_once()

    def test_false_when_capture_will_not_open(self, video_path: Path) -> None:
        """An unopenable file is not readable."""
        with patch("cv2.VideoCapture", return_value=_capture(False, None)):
            assert is_opencv_readable(video_path) is False


class TestTranscodeToH264:
    """Tests for transcode_to_h264."""

    def test_raises_when_ffmpeg_fails(self, video_path: Path, tmp_path: Path) -> None:
        """A non-zero ffmpeg exit is surfaced with its stderr."""
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="bad input")
        with (
            patch("subprocess.run", return_value=failed),
            pytest.raises(RuntimeError, match="bad input"),
        ):
            transcode_to_h264(video_path, tmp_path / "out.mp4")

    def test_raises_when_ffmpeg_missing(self, video_path: Path, tmp_path: Path) -> None:
        """A missing ffmpeg binary is reported rather than raising FileNotFoundError."""
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(RuntimeError, match="ffmpeg is not installed"),
        ):
            transcode_to_h264(video_path, tmp_path / "out.mp4")


class TestEnsureOpenCVReadable:
    """Tests for ensure_opencv_readable."""

    def test_readable_video_is_returned_untouched(self, video_path: Path) -> None:
        """No transcode happens when OpenCV can already decode the video."""
        with (
            patch(f"{MODULE}.is_opencv_readable", return_value=True),
            patch(f"{MODULE}.transcode_to_h264") as mock_transcode,
        ):
            assert ensure_opencv_readable(video_path) == video_path
        mock_transcode.assert_not_called()

    def test_undecodable_video_is_transcoded(self, video_path: Path) -> None:
        """An undecodable video is re-encoded and the new path returned."""
        expected = video_path.with_name("original_h264.mp4")
        # Unreadable source, then readable result after the transcode.
        with (
            patch(f"{MODULE}.is_opencv_readable", side_effect=[False, True]),
            patch(f"{MODULE}.transcode_to_h264") as mock_transcode,
        ):
            assert ensure_opencv_readable(video_path) == expected
        mock_transcode.assert_called_once_with(video_path, expected)

    def test_existing_transcode_is_reused(self, video_path: Path) -> None:
        """A previous transcode is reused instead of re-encoding."""
        existing = video_path.with_name("original_h264.mp4")
        existing.touch()
        with (
            patch(f"{MODULE}.is_opencv_readable", side_effect=[False, True]),
            patch(f"{MODULE}.transcode_to_h264") as mock_transcode,
        ):
            assert ensure_opencv_readable(video_path) == existing
        mock_transcode.assert_not_called()

    def test_raises_when_transcode_output_is_still_unreadable(self, video_path: Path) -> None:
        """A transcode that produces an unusable file is an error, not a silent pass."""
        with (
            patch(f"{MODULE}.is_opencv_readable", return_value=False),
            patch(f"{MODULE}.transcode_to_h264"),
            pytest.raises(RuntimeError, match="still unreadable"),
        ):
            ensure_opencv_readable(video_path)
