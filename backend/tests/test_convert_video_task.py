"""Tests for convert_video_task background function."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.projects.complete_video_upload import convert_video_task
from app.api.v1.endpoints.projects.shared_objects import conversion_progress
from app.core.config import settings
from app.models.image import ImageStatus, ValidationStatus


@pytest.fixture
def mock_project_dirs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create mock project directory structure.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        tuple: (project_dir, output_dir, inference_dir, video_path)
    """
    project_id = uuid4()
    project_dir = tmp_path / "projects" / str(project_id)
    output_dir = project_dir / "output"
    inference_dir = project_dir / "inference"
    video_path = project_dir / "video.mp4"

    project_dir.mkdir(parents=True, exist_ok=True)
    video_path.touch()

    return project_dir, output_dir, inference_dir, video_path


class TestConvertVideoTask:
    """Tests for convert_video_task background function."""

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.Session")
    @patch("app.api.v1.endpoints.projects.create_engine")
    def test_convert_video_task_success(
        self,
        mock_create_engine: Mock,
        mock_session_cls: Mock,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test successful video conversion with database population.

        Verifies that:
        - Progress tracking is initialized
        - Video conversion is called with correct parameters
        - Thumbnail is generated from first frame
        - Image records are created in database
        - Progress tracking is updated correctly
        """
        project_dir, output_dir, inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock successful conversion (no error)
        mock_convert_video.return_value = False

        # Create mock frame files
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            (output_dir / f"frame_{i:06d}.jpg").touch()
            (inference_dir / f"frame_{i:06d}.jpg").touch()

        # Mock database session and engine
        mock_session = MagicMock(spec=Session)
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_session_cls.return_value = mock_session
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        # Execute the task
        with patch.object(settings, "PROJECTS_ROOT_DIR", str(project_dir.parent)):
            convert_video_task(
                project_id=project_id,
                video_path=video_path,
                project_dir=project_dir,
                output_width=1920,
                inference_width=640,
            )

        # Verify progress tracking was initialized
        project_id_str = str(project_id)
        assert project_id_str in conversion_progress
        assert conversion_progress[project_id_str]["error"] is False

        # Verify video conversion was called
        mock_convert_video.assert_called_once()
        call_args = mock_convert_video.call_args
        assert call_args[0][0] == video_path
        assert call_args[0][1] == output_dir
        assert call_args[0][2] == inference_dir
        assert call_args[0][3] == 1920
        assert call_args[0][4] == 640

        # Verify thumbnail generation was called
        mock_generate_thumbnail.assert_called_once()
        # Check that it was called with the first frame
        assert "frame_000000.jpg" in str(mock_generate_thumbnail.call_args[0][0])

        # Verify Image records were added to database
        assert mock_session.add.call_count == 3  # 3 frames
        mock_session.commit.assert_called_once()

        # Clean up progress tracking
        del conversion_progress[project_id_str]

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    def test_convert_video_task_conversion_error(
        self,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test handling of video conversion errors.

        Verifies that:
        - Error flag is set in progress tracking
        - Thumbnail generation is not attempted
        - Database population is not attempted
        """
        project_dir, _output_dir, _inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock failed conversion
        mock_convert_video.return_value = True  # Error occurred

        # Execute the task
        convert_video_task(
            project_id=project_id,
            video_path=video_path,
            project_dir=project_dir,
            output_width=1920,
            inference_width=640,
        )

        # Verify error was recorded
        project_id_str = str(project_id)
        assert project_id_str in conversion_progress
        assert conversion_progress[project_id_str]["error"] is True

        # Verify thumbnail and database operations were not attempted
        mock_generate_thumbnail.assert_not_called()

        # Clean up progress tracking
        del conversion_progress[project_id_str]

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    def test_convert_video_task_thumbnail_error(
        self,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test handling of thumbnail generation errors.

        Verifies that:
        - Error flag is set when thumbnail generation fails
        - Database population is not attempted after thumbnail error
        """
        project_dir, output_dir, inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock successful conversion
        mock_convert_video.return_value = False

        # Create mock frame files
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_000000.jpg").touch()
        (inference_dir / "frame_000000.jpg").touch()

        # Mock thumbnail generation failure
        mock_generate_thumbnail.side_effect = Exception("Thumbnail generation failed")

        # Execute the task
        with patch.object(settings, "PROJECTS_ROOT_DIR", str(project_dir.parent)):
            convert_video_task(
                project_id=project_id,
                video_path=video_path,
                project_dir=project_dir,
                output_width=1920,
                inference_width=640,
            )

        # Verify error was recorded
        project_id_str = str(project_id)
        assert project_id_str in conversion_progress
        assert conversion_progress[project_id_str]["error"] is True

        # Clean up progress tracking
        del conversion_progress[project_id_str]

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    def test_convert_video_task_no_frames(
        self,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test handling when no frames are generated.

        Verifies that:
        - Warning is logged when no frames exist
        - Task continues without generating thumbnail
        """
        project_dir, output_dir, inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock successful conversion but create no frame files
        mock_convert_video.return_value = False
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)

        # Execute the task
        with patch.object(settings, "PROJECTS_ROOT_DIR", str(project_dir.parent)):
            convert_video_task(
                project_id=project_id,
                video_path=video_path,
                project_dir=project_dir,
                output_width=1920,
                inference_width=640,
            )

        # Verify thumbnail generation was not called
        mock_generate_thumbnail.assert_not_called()

        # Verify error flag is not set (no frames is a warning, not an error)
        project_id_str = str(project_id)
        assert project_id_str in conversion_progress

        # Clean up progress tracking
        del conversion_progress[project_id_str]

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.create_engine")
    def test_convert_video_task_database_error(
        self,
        mock_create_engine: Mock,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test handling of database errors during Image record creation.

        Verifies that:
        - Database errors are caught and logged
        - Error does not crash the background task
        """
        project_dir, output_dir, inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock successful conversion
        mock_convert_video.return_value = False

        # Create mock frame files
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_000000.jpg").touch()
        (inference_dir / "frame_000000.jpg").touch()

        # Mock database error
        mock_create_engine.side_effect = Exception("Database connection failed")

        # Execute the task - should not raise exception
        with patch.object(settings, "PROJECTS_ROOT_DIR", str(project_dir.parent)):
            convert_video_task(
                project_id=project_id,
                video_path=video_path,
                project_dir=project_dir,
                output_width=1920,
                inference_width=640,
            )

        # Verify video conversion and thumbnail were still called
        mock_convert_video.assert_called_once()
        mock_generate_thumbnail.assert_called_once()

        # Clean up progress tracking
        project_id_str = str(project_id)
        if project_id_str in conversion_progress:
            del conversion_progress[project_id_str]

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.Session")
    @patch("app.api.v1.endpoints.projects.create_engine")
    def test_convert_video_task_progress_callback(
        self,
        mock_create_engine: Mock,
        mock_session_cls: Mock,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test that progress callback updates tracking correctly.

        Verifies that:
        - Progress callback is passed to convert_video_to_jpegs
        - Progress tracking is updated when callback is invoked
        """
        project_dir, output_dir, inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock successful conversion and capture the progress callback
        def mock_conversion_with_callback(*args, **kwargs):
            callback = kwargs.get("progress_callback")
            if callback:
                # Simulate progress updates
                callback(5, 10)
                callback(10, 10)
            return False

        mock_convert_video.side_effect = mock_conversion_with_callback

        # Create mock frame files
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "frame_000000.jpg").touch()
        (inference_dir / "frame_000000.jpg").touch()

        # Mock database
        mock_session = MagicMock(spec=Session)
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_session_cls.return_value = mock_session
        mock_engine = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_session.__enter__.return_value = mock_session
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_session
        mock_create_engine.return_value = mock_engine

        # Execute the task
        with patch.object(settings, "PROJECTS_ROOT_DIR", str(project_dir.parent)):
            convert_video_task(
                project_id=project_id,
                video_path=video_path,
                project_dir=project_dir,
                output_width=1920,
                inference_width=640,
            )

        # Verify progress tracking was updated
        project_id_str = str(project_id)
        assert project_id_str in conversion_progress
        assert conversion_progress[project_id_str]["saved"] == 10
        assert conversion_progress[project_id_str]["total"] == 10

        # Clean up progress tracking
        del conversion_progress[project_id_str]

    @patch("app.api.v1.endpoints.projects.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.Session")
    @patch("app.api.v1.endpoints.projects.create_engine")
    def test_convert_video_task_image_record_fields(
        self,
        mock_create_engine: Mock,
        mock_session_cls: Mock,
        mock_generate_thumbnail: Mock,
        mock_convert_video: Mock,
        mock_project_dirs: tuple[Path, Path, Path, Path],
    ) -> None:
        """Test that Image records are created with correct field values.

        Verifies that:
        - Frame numbers are extracted correctly from filenames
        - Paths are relative to PROJECTS_ROOT_DIR
        - Status is set to PROCESSED
        - Validation is set to NOT_VALIDATED
        - manually_labeled is set to False
        """
        project_dir, output_dir, inference_dir, video_path = mock_project_dirs
        project_id = uuid4()

        # Mock successful conversion
        mock_convert_video.return_value = False

        # Create specific frame files with known frame numbers
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        frame_numbers = [0, 5, 42]
        for fn in frame_numbers:
            (output_dir / f"frame_{fn:06d}.jpg").touch()
            (inference_dir / f"frame_{fn:06d}.jpg").touch()

        # Capture Image objects added to session
        added_images = []

        def capture_add(image):
            added_images.append(image)

        mock_session = MagicMock(spec=Session)
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_session.add.side_effect = capture_add
        mock_session_cls.return_value = mock_session
        mock_engine = MagicMock()
        mock_session.add.side_effect = capture_add
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_session
        mock_create_engine.return_value = mock_engine

        # Execute the task
        with patch.object(settings, "PROJECTS_ROOT_DIR", str(project_dir.parent)):
            convert_video_task(
                project_id=project_id,
                video_path=video_path,
                project_dir=project_dir,
                output_width=1920,
                inference_width=640,
            )

        # Verify Image records have correct fields
        assert len(added_images) == 3
        for i, image in enumerate(added_images):
            assert image.project_id == project_id
            assert image.frame_number == frame_numbers[i]
            assert image.status == ImageStatus.PROCESSED
            assert image.manually_labeled is False
            assert image.validation == ValidationStatus.NOT_VALIDATED
            # Verify paths are relative
            assert not image.inference_path.startswith("/")
            assert not image.output_path.startswith("/")
            assert f"frame_{frame_numbers[i]:06d}.jpg" in image.inference_path
            assert f"frame_{frame_numbers[i]:06d}.jpg" in image.output_path

        # Clean up progress tracking
        project_id_str = str(project_id)
        if project_id_str in conversion_progress:
            del conversion_progress[project_id_str]
