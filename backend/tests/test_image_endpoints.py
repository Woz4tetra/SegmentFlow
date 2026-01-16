"""Tests for image/frame endpoints."""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image import Image, ImageStatus, ValidationStatus
from app.models.project import Project


@pytest_asyncio.fixture
async def test_project(db: AsyncSession) -> Project:
    """Create a test project.

    Args:
        db: Database session

    Returns:
        Project: Created test project
    """
    project = Project(
        name="Test Project",
        active=True,
        stage="manual_labeling",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest_asyncio.fixture
async def test_project_with_images(
    db: AsyncSession,
    test_project: Project,
) -> tuple[Project, list[Image]]:
    """Create a test project with images.

    Args:
        db: Database session
        test_project: Test project fixture

    Returns:
        tuple: (project, list of images)
    """
    images = []
    for i in range(5):
        image = Image(
            project_id=test_project.id,
            frame_number=i,
            inference_path=f"{test_project.id}/inference/frame_{i:06d}.jpg",
            output_path=f"{test_project.id}/output/frame_{i:06d}.jpg",
            status=ImageStatus.PROCESSED,
            manually_labeled=False,
            validation=ValidationStatus.NOT_VALIDATED,
        )
        db.add(image)
        images.append(image)

    await db.commit()
    for image in images:
        await db.refresh(image)

    return test_project, images


@pytest.fixture
def create_mock_frame_files(tmp_path: Path):
    """Factory fixture to create mock frame files for any project.

    Args:
        tmp_path: pytest temporary path

    Returns:
        Callable that creates frame files and returns the root path
    """

    def _create(project_id: str) -> Path:
        project_dir = tmp_path / project_id
        inference_dir = project_dir / "inference"
        output_dir = project_dir / "output"

        inference_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create mock frame files
        for i in range(5):
            (inference_dir / f"frame_{i:06d}.jpg").write_bytes(b"fake jpeg data")
            (output_dir / f"frame_{i:06d}.jpg").write_bytes(b"fake jpeg data")

        return tmp_path

    return _create


class TestListProjectImages:
    """Tests for GET /projects/{project_id}/images endpoint."""

    @pytest.mark.asyncio
    async def test_list_project_images_success(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        test_project_with_images: tuple[Project, list[Image]],
    ) -> None:
        """Test successfully listing images for a project.

        Verifies that:
        - All images are returned
        - Images are ordered by frame number
        - All image fields are present
        - Total count is correct
        """
        project, _images = test_project_with_images

        response = await client.get(f"/api/v1/projects/{project.id}/images")
        assert response.status_code == 200

        data = response.json()
        assert "images" in data
        assert "total" in data
        assert data["total"] == 5
        assert len(data["images"]) == 5

        # Verify images are ordered by frame number
        for i, img_data in enumerate(data["images"]):
            assert img_data["frame_number"] == i
            assert img_data["status"] == "processed"
            assert img_data["manually_labeled"] is False
            assert img_data["validation"] == "not_validated"
            assert "id" in img_data
            assert "inference_path" in img_data
            assert "output_path" in img_data

    @pytest.mark.asyncio
    async def test_list_project_images_empty(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        test_project: Project,
    ) -> None:
        """Test listing images for a project with no images.

        Verifies that:
        - Empty list is returned
        - Total count is 0
        - Request is successful
        """
        response = await client.get(f"/api/v1/projects/{test_project.id}/images")
        assert response.status_code == 200

        data = response.json()
        assert data["images"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_project_images_project_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test listing images for non-existent project returns 404.

        Verifies proper error handling for missing project.
        """
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/projects/{fake_id}/images")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_project_images_invalid_uuid(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test listing images with invalid UUID format returns 422.

        Verifies validation of UUID format.
        """
        response = await client.get("/api/v1/projects/not-a-uuid/images")
        assert response.status_code == 422


class TestGetFrameImage:
    """Tests for GET /projects/{project_id}/frames/{frame_number} endpoint."""

    @pytest.mark.asyncio
    async def test_get_frame_image_success(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        test_project: Project,
        create_mock_frame_files,
    ) -> None:
        """Test successfully retrieving a frame image.

        Verifies that:
        - Frame image is returned
        - Content type is image/jpeg
        - Cache headers are set
        """
        mock_root = create_mock_frame_files(str(test_project.id))

        with patch(
            "app.api.v1.endpoints.projects.get_frame_image.settings.PROJECTS_ROOT_DIR",
            str(mock_root),
        ):
            response = await client.get(f"/api/v1/projects/{test_project.id}/frames/0")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert "Cache-Control" in response.headers
        assert response.content == b"fake jpeg data"

    @pytest.mark.asyncio
    async def test_get_frame_image_multiple_frames(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        test_project: Project,
        create_mock_frame_files,
    ) -> None:
        """Test retrieving different frame numbers.

        Verifies that different frame numbers can be accessed.
        """
        mock_root = create_mock_frame_files(str(test_project.id))

        with patch(
            "app.api.v1.endpoints.projects.get_frame_image.settings.PROJECTS_ROOT_DIR",
            str(mock_root),
        ):
            for frame_num in [0, 2, 4]:
                response = await client.get(
                    f"/api/v1/projects/{test_project.id}/frames/{frame_num}"
                )
                assert response.status_code == 200
                assert response.headers["content-type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_frame_image_frame_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        test_project: Project,
        create_mock_frame_files,
    ) -> None:
        """Test requesting non-existent frame returns 404.

        Verifies proper error handling for missing frame files.
        """
        mock_root = create_mock_frame_files(str(test_project.id))

        with patch(
            "app.api.v1.endpoints.projects.get_frame_image.settings.PROJECTS_ROOT_DIR",
            str(mock_root),
        ):
            response = await client.get(f"/api/v1/projects/{test_project.id}/frames/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_frame_image_project_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        tmp_path: Path,
    ) -> None:
        """Test requesting frame for non-existent project returns 404.

        Verifies proper error handling for missing project.
        """
        fake_id = str(uuid4())

        with patch(
            "app.api.v1.endpoints.projects.get_frame_image.settings.PROJECTS_ROOT_DIR",
            str(tmp_path),
        ):
            response = await client.get(f"/api/v1/projects/{fake_id}/frames/0")

        assert response.status_code == 404
        assert "project" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_frame_image_invalid_project_uuid(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test invalid project UUID format returns 422.

        Verifies validation of UUID format.
        """
        response = await client.get("/api/v1/projects/not-a-uuid/frames/0")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_frame_image_negative_frame_number(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
        test_project: Project,
        create_mock_frame_files,
    ) -> None:
        """Test requesting negative frame number.

        Negative frame numbers should result in file not found.
        """
        mock_root = create_mock_frame_files(str(test_project.id))

        with patch(
            "app.api.v1.endpoints.projects.get_frame_image.settings.PROJECTS_ROOT_DIR",
            str(mock_root),
        ):
            response = await client.get(f"/api/v1/projects/{test_project.id}/frames/-1")

        # Should get 404 since negative frame files don't exist
        assert response.status_code == 404
