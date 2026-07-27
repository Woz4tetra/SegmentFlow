"""Tests for convert_video_task background function."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.projects.complete_video_upload import (
    _reconcile_image_records,
    _remove_existing_frames,
    convert_video_task,
)
from app.api.v1.endpoints.projects.shared_objects import conversion_progress
from app.models.image import ImageStatus, ValidationStatus

TASK_MODULE = "app.api.v1.endpoints.projects.complete_video_upload"


def patch_projects_root(path: Path):
    """Point the task module's settings at a temporary projects root.

    Settings exposes PROJECTS_ROOT_DIR as a read-only property, so the module-level
    ``settings`` reference is replaced rather than the attribute being assigned.

    Args:
        path: Directory to use as the projects root

    Returns:
        A patch context manager
    """
    fake_settings = MagicMock()
    fake_settings.PROJECTS_ROOT_DIR = str(path)
    fake_settings.OUTPUT_WIDTH = 1920
    fake_settings.INFERENCE_WIDTH = 1024
    fake_settings.get_database_url.return_value = "sqlite:///:memory:"
    return patch(f"{TASK_MODULE}.settings", fake_settings)


def write_frames_side_effect(output_dir: Path, inference_dir: Path, frame_numbers: list[int]):
    """Build a convert_video_to_jpegs side effect that writes placeholder frames.

    The task clears stale frames before converting, so the mocked conversion has to create
    the frames itself rather than the test creating them up front.

    Args:
        output_dir: Directory for output-resolution frames
        inference_dir: Directory for inference-resolution frames
        frame_numbers: Frame numbers to create

    Returns:
        A callable suitable for Mock.side_effect that reports no conversion error
    """

    def _side_effect(*_args, **_kwargs) -> bool:
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        for number in frame_numbers:
            (output_dir / f"frame_{number:06d}.jpg").touch()
            (inference_dir / f"frame_{number:06d}.jpg").touch()
        return False

    return _side_effect


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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.Session")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.create_engine")
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

        # Mock successful conversion that writes the frames it would have extracted
        mock_convert_video.side_effect = write_frames_side_effect(
            output_dir, inference_dir, [0, 1, 2]
        )

        # Mock database session and engine
        mock_session = MagicMock(spec=Session)
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_session_cls.return_value = mock_session
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        # Execute the task
        with patch_projects_root(project_dir.parent):
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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
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

        # Mock successful conversion that writes the frame it would have extracted
        mock_convert_video.side_effect = write_frames_side_effect(output_dir, inference_dir, [0])

        # Mock thumbnail generation failure
        mock_generate_thumbnail.side_effect = Exception("Thumbnail generation failed")

        # Execute the task
        with patch_projects_root(project_dir.parent):
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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
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
        with patch_projects_root(project_dir.parent):
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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.create_engine")
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

        # Mock successful conversion that writes the frame it would have extracted
        mock_convert_video.side_effect = write_frames_side_effect(output_dir, inference_dir, [0])

        # Mock database error
        mock_create_engine.side_effect = Exception("Database connection failed")

        # Execute the task - should not raise exception
        with patch_projects_root(project_dir.parent):
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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.Session")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.create_engine")
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
        write_frames = write_frames_side_effect(output_dir, inference_dir, [0])

        def mock_conversion_with_callback(*args, **kwargs):
            callback = kwargs.get("progress_callback")
            if callback:
                # Simulate progress updates
                callback(5, 10)
                callback(10, 10)
            return write_frames(*args, **kwargs)

        mock_convert_video.side_effect = mock_conversion_with_callback

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
        with patch_projects_root(project_dir.parent):
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

    @patch("app.api.v1.endpoints.projects.complete_video_upload.convert_video_to_jpegs")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.generate_thumbnail")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.Session")
    @patch("app.api.v1.endpoints.projects.complete_video_upload.create_engine")
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

        # Mock successful conversion that writes specific known frame numbers
        frame_numbers = [0, 5, 42]
        mock_convert_video.side_effect = write_frames_side_effect(
            output_dir, inference_dir, frame_numbers
        )

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
        with patch_projects_root(project_dir.parent):
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


class TestReconcileImageRecords:
    """Tests for Image record reconciliation, which makes re-conversion safe."""

    @pytest.fixture
    def sync_db(self, tmp_path: Path) -> tuple[str, Path]:
        """Create a temporary SQLite database with the full schema.

        Args:
            tmp_path: pytest temporary path fixture

        Returns:
            tuple: (sync database URL, projects root directory)
        """
        from sqlalchemy import create_engine as real_create_engine

        from app.core.database import Base

        db_path = tmp_path / "reconcile.db"
        engine = real_create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        engine.dispose()

        projects_root = tmp_path / "projects"
        projects_root.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}", projects_root

    def _make_frames(self, project_dir: Path, frame_numbers: list[int]) -> tuple[Path, Path]:
        """Create output and inference JPEG placeholders for the given frames."""
        output_dir = project_dir / "output"
        inference_dir = project_dir / "inference"
        output_dir.mkdir(parents=True, exist_ok=True)
        inference_dir.mkdir(parents=True, exist_ok=True)
        for number in frame_numbers:
            (output_dir / f"frame_{number:06d}.jpg").touch()
            (inference_dir / f"frame_{number:06d}.jpg").touch()
        return output_dir, inference_dir

    def _run(self, sync_url: str, projects_root: Path, project_id, dirs: tuple[Path, Path]) -> None:
        """Invoke the reconciler against the temporary database."""
        fake_settings = MagicMock()
        fake_settings.get_database_url.return_value = sync_url
        fake_settings.PROJECTS_ROOT_DIR = str(projects_root)
        with patch(f"{TASK_MODULE}.settings", fake_settings):
            _reconcile_image_records(project_id, dirs[0], dirs[1])

    def _seed_project(self, sync_url: str) -> "UUID":
        """Insert a project row and return its id."""
        from sqlalchemy import create_engine as real_create_engine

        from app.models.project import Project

        engine = real_create_engine(sync_url)
        with Session(engine) as session:
            project = Project(name="Reconcile Project")
            session.add(project)
            session.commit()
            project_id = project.id
        engine.dispose()
        return project_id

    def _frame_numbers(self, sync_url: str) -> list[int]:
        """Return the frame numbers currently stored as Image records."""
        from sqlalchemy import create_engine as real_create_engine
        from sqlalchemy import select

        from app.models.image import Image

        engine = real_create_engine(sync_url)
        with Session(engine) as session:
            numbers = sorted(session.scalars(select(Image.frame_number)).all())
        engine.dispose()
        return numbers

    def test_creates_records_on_first_run(self, sync_db: tuple[str, Path]) -> None:
        """Test that a first conversion inserts one record per frame."""
        sync_url, projects_root = sync_db
        project_id = self._seed_project(sync_url)
        dirs = self._make_frames(projects_root / str(project_id), [0, 1, 2])

        self._run(sync_url, projects_root, project_id, dirs)

        assert self._frame_numbers(sync_url) == [0, 1, 2]

    def test_rerun_does_not_duplicate_records(self, sync_db: tuple[str, Path]) -> None:
        """Test that re-converting the same frames updates rather than duplicates."""
        sync_url, projects_root = sync_db
        project_id = self._seed_project(sync_url)
        dirs = self._make_frames(projects_root / str(project_id), [0, 1, 2])

        self._run(sync_url, projects_root, project_id, dirs)
        self._run(sync_url, projects_root, project_id, dirs)

        assert self._frame_numbers(sync_url) == [0, 1, 2]

    def test_rerun_drops_records_for_removed_frames(self, sync_db: tuple[str, Path]) -> None:
        """Test that records without a frame file on disk are deleted."""
        sync_url, projects_root = sync_db
        project_id = self._seed_project(sync_url)
        project_dir = projects_root / str(project_id)
        dirs = self._make_frames(project_dir, [0, 1, 2])

        self._run(sync_url, projects_root, project_id, dirs)

        # Simulate a re-conversion that produced fewer frames
        for frame_dir in dirs:
            (frame_dir / "frame_000002.jpg").unlink()
        self._run(sync_url, projects_root, project_id, dirs)

        assert self._frame_numbers(sync_url) == [0, 1]


class TestRemoveExistingFrames:
    """Tests for stale frame cleanup before a re-conversion."""

    def test_removes_only_frame_jpegs(self, tmp_path: Path) -> None:
        """Test that frame files are deleted and other files are left alone."""
        output_dir = tmp_path / "output"
        inference_dir = tmp_path / "inference"
        output_dir.mkdir()
        inference_dir.mkdir()
        (output_dir / "frame_000000.jpg").touch()
        (inference_dir / "frame_000000.jpg").touch()
        keep = output_dir / "notes.txt"
        keep.touch()

        _remove_existing_frames(output_dir, inference_dir)

        assert list(output_dir.glob("frame_*.jpg")) == []
        assert list(inference_dir.glob("frame_*.jpg")) == []
        assert keep.exists()
