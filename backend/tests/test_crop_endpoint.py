"""Tests for the project crop endpoint."""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.video_frames import VideoInfo
from app.models.image import Image, ImageStatus, ValidationStatus
from app.models.label import Label
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project

MODULE = "app.api.v1.endpoints.projects.set_crop_region"


@pytest.fixture
def source_video(tmp_path: Path) -> Path:
    """Create a placeholder video file on disk.

    Args:
        tmp_path: pytest temporary path fixture

    Returns:
        Path: Path to the placeholder video
    """
    video_path = tmp_path / "original.mp4"
    video_path.touch()
    return video_path


def _video_info(video_path: Path, width: int = 1920, height: int = 1080) -> VideoInfo:
    """Build a VideoInfo stub for the given dimensions."""
    return VideoInfo(path=video_path, fps=30.0, frame_count=300, width=width, height=height)


async def _create_project(db: AsyncSession, video_path: Path | None) -> Project:
    """Insert a project pointing at the given video."""
    project = Project(
        name="Crop Project",
        video_path=str(video_path) if video_path else None,
        stage="trim",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


class TestSetCropValidation:
    """Validation behaviour for POST /projects/{id}/crop."""

    @pytest.mark.asyncio
    async def test_project_not_found(self, client: AsyncIterator[AsyncClient]) -> None:
        response = await client.post(
            f"/api/v1/projects/{uuid4()}/crop",
            json={"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_project_without_video(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
    ) -> None:
        project = await _create_project(db, None)
        response = await client.post(
            f"/api/v1/projects/{project.id}/crop",
            json={"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_partial_rectangle_rejected(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)
        response = await client.post(
            f"/api/v1/projects/{project.id}/crop",
            json={"x": 0.1, "y": 0.1, "width": 0.5, "height": None},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rectangle_past_frame_boundary_rejected(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)
        response = await client.post(
            f"/api/v1/projects/{project.id}/crop",
            json={"x": 0.8, "y": 0.0, "width": 0.5, "height": 0.5},
        )
        assert response.status_code == 422
        assert "boundary" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rectangle_below_minimum_size_rejected(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)
        with patch(f"{MODULE}.get_video_info", return_value=_video_info(source_video)):
            response = await client.post(
                f"/api/v1/projects/{project.id}/crop",
                # 0.001 * 1920 = ~2 source pixels, below the 16px minimum
                json={"x": 0.0, "y": 0.0, "width": 0.001, "height": 0.5},
            )
        assert response.status_code == 422
        assert "at least" in response.json()["detail"]


class TestSetCropApply:
    """Applying, changing, and clearing the crop."""

    @pytest.mark.asyncio
    async def test_apply_crop_stores_rect_and_starts_conversion(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)
        start_conversion = MagicMock()

        with (
            patch(f"{MODULE}.get_video_info", return_value=_video_info(source_video)),
            patch(f"{MODULE}.start_conversion_background", start_conversion),
        ):
            response = await client.post(
                f"/api/v1/projects/{project.id}/crop",
                json={"x": 0.25, "y": 0.1, "width": 0.5, "height": 0.5},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["crop_x"] == 0.25
        assert data["crop_y"] == 0.1
        assert data["crop_width"] == 0.5
        assert data["crop_height"] == 0.5
        start_conversion.assert_called_once()

        await db.refresh(project)
        assert project.crop_x == 0.25
        assert project.crop_height == 0.5

    @pytest.mark.asyncio
    async def test_unchanged_crop_skips_conversion(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)
        project.crop_x = 0.25
        project.crop_y = 0.1
        project.crop_width = 0.5
        project.crop_height = 0.5
        await db.commit()

        start_conversion = MagicMock()
        with (
            patch(f"{MODULE}.get_video_info", return_value=_video_info(source_video)),
            patch(f"{MODULE}.start_conversion_background", start_conversion),
        ):
            response = await client.post(
                f"/api/v1/projects/{project.id}/crop",
                json={"x": 0.25, "y": 0.1, "width": 0.5, "height": 0.5},
            )

        assert response.status_code == 200
        start_conversion.assert_not_called()

    @pytest.mark.asyncio
    async def test_clearing_crop_nulls_columns(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)
        project.crop_x = 0.25
        project.crop_y = 0.1
        project.crop_width = 0.5
        project.crop_height = 0.5
        await db.commit()

        start_conversion = MagicMock()
        with (
            patch(f"{MODULE}.get_video_info", return_value=_video_info(source_video)),
            patch(f"{MODULE}.start_conversion_background", start_conversion),
        ):
            response = await client.post(
                f"/api/v1/projects/{project.id}/crop",
                json={"x": None, "y": None, "width": None, "height": None},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["crop_x"] is None
        assert data["crop_width"] is None
        start_conversion.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_crop_clears_masks_and_points(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
    ) -> None:
        project = await _create_project(db, source_video)

        label = Label(name="robot", color_hex="#ff0000")
        image = Image(
            project_id=project.id,
            frame_number=0,
            inference_path="inference/frame_000000.jpg",
            output_path="output/frame_000000.jpg",
            status=ImageStatus.PROCESSED,
            manually_labeled=True,
            validation=ValidationStatus.PASSED,
        )
        db.add_all([label, image])
        await db.commit()
        await db.refresh(label)
        await db.refresh(image)

        db.add_all(
            [
                Mask(
                    image_id=image.id,
                    label_id=label.id,
                    contour_polygon={"contours": [[[0, 0], [1, 0], [1, 1]]], "hierarchy": []},
                    area=1.0,
                ),
                LabeledPoint(image_id=image.id, label_id=label.id, x=5.0, y=5.0, include=True),
            ]
        )
        await db.commit()

        with (
            patch(f"{MODULE}.get_video_info", return_value=_video_info(source_video)),
            patch(f"{MODULE}.start_conversion_background", MagicMock()),
        ):
            response = await client.post(
                f"/api/v1/projects/{project.id}/crop",
                json={"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5},
            )

        assert response.status_code == 200

        remaining_masks = (await db.execute(select(Mask))).scalars().all()
        remaining_points = (await db.execute(select(LabeledPoint))).scalars().all()
        assert remaining_masks == []
        assert remaining_points == []

        await db.refresh(image)
        assert image.manually_labeled is False
        assert image.validation == ValidationStatus.NOT_VALIDATED.value

    @pytest.mark.asyncio
    async def test_apply_crop_removes_thumbnail(
        self,
        client: AsyncIterator[AsyncClient],
        db: AsyncSession,
        source_video: Path,
        tmp_path: Path,
    ) -> None:
        project = await _create_project(db, source_video)

        projects_root = tmp_path / "projects"
        thumbnail_path = projects_root / str(project.id) / "thumbnail.jpg"
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        thumbnail_path.touch()

        fake_settings = MagicMock()
        fake_settings.PROJECTS_ROOT_DIR = str(projects_root)
        fake_settings.OUTPUT_WIDTH = 1920
        fake_settings.INFERENCE_WIDTH = 1024

        with (
            patch(f"{MODULE}.get_video_info", return_value=_video_info(source_video)),
            patch(f"{MODULE}.start_conversion_background", MagicMock()),
            patch(f"{MODULE}.settings", fake_settings),
        ):
            response = await client.post(
                f"/api/v1/projects/{project.id}/crop",
                json={"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5},
            )

        assert response.status_code == 200
        assert not thumbnail_path.exists()
