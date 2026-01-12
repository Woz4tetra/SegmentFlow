"""Database schema creation tests for DATA-001."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.schemas import LabelBase, LabelUpdate, ProjectUpdate
from app.core.database import AsyncSessionLocal, engine, init_db
from app.models import Image, Label, LabeledPoint, Mask, Project, Stats


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _init_db() -> AsyncIterator[None]:
    """Initialize database once per module and dispose after tests."""

    await init_db()
    try:
        yield
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_schema_tables_and_fks_created() -> None:
    """Ensure all planned tables and their foreign keys are created."""

    async with engine.begin() as conn:

        def _assert_schema(sync_conn) -> None:
            inspector = inspect(sync_conn)

            expected_tables = {
                "projects",
                "labels",
                "images",
                "labeled_points",
                "masks",
                "stats",
                "user_settings",
            }

            tables = set(inspector.get_table_names())
            assert expected_tables.issubset(tables)

            def _has_fk(table: str, column: str, target: str) -> bool:
                fks = inspector.get_foreign_keys(table)
                return any(
                    column in fk.get("constrained_columns", [])
                    and fk.get("referred_table") == target
                    for fk in fks
                )

            # Labels are now global - no project_id FK
            assert _has_fk("images", "project_id", "projects")
            assert _has_fk("labeled_points", "image_id", "images")
            assert _has_fk("labeled_points", "label_id", "labels")
            assert _has_fk("masks", "image_id", "images")
            assert _has_fk("masks", "label_id", "labels")
            assert _has_fk("stats", "project_id", "projects")
            assert _has_fk("stats", "image_id", "images")

        await conn.run_sync(_assert_schema)


@pytest.mark.asyncio
async def test_foreign_keys_enforced() -> None:
    """Inserting child rows without parents should violate FK constraints."""

    async with AsyncSessionLocal() as session:
        # Labels are now global - test with images instead
        bad_image = Image(project_id=uuid4(), frame_number=1, inference_path="/tmp/test.jpg")

        session.add(bad_image)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_removes_children() -> None:
    """Deleting a project cascades to related images, points, masks, stats (but not labels - they're global)."""

    async with AsyncSessionLocal() as session:
        project = Project(name="test-project")
        label = Label(name="person", color_hex="#00ff00")  # Global label - no project reference
        image = Image(project=project, frame_number=1, inference_path="/tmp/i.jpg")
        point = LabeledPoint(image=image, label=label, x=0.5, y=0.6, include=True)
        mask = Mask(image=image, label=label, contour_polygon={"points": []}, area=1.0)
        stats = Stats(project=project, image=image, time_spent_ms=10, propagation_time_ms=0)

        session.add_all([project, label, image, point, mask, stats])
        await session.commit()

        await session.delete(project)
        await session.commit()

    async with AsyncSessionLocal() as session:
        # Project and its children should be deleted
        for model in (Project, Image, LabeledPoint, Mask, Stats):
            count = await session.scalar(select(func.count()).select_from(model))
            assert count == 0

        # Label should still exist (global)
        label_count = await session.scalar(select(func.count()).select_from(Label))
        assert label_count == 1


@pytest.mark.asyncio
async def test_project_update_stage_validation() -> None:
    """Test ProjectUpdate schema validates stage values."""
    # Valid stage
    valid_update = ProjectUpdate(stage="upload")
    assert valid_update.stage == "upload"

    # Invalid stage should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        ProjectUpdate(stage="invalid_stage")
    assert "Invalid stage" in str(exc_info.value)


@pytest.mark.asyncio
async def test_label_color_hex_validation() -> None:
    """Test LabelBase and LabelUpdate validate color hex format."""
    # Valid color
    valid_label = LabelBase(name="test", color_hex="#ff0000")
    assert valid_label.color_hex == "#ff0000"

    # Invalid format - not starting with #
    with pytest.raises(ValidationError) as exc_info:
        LabelBase(name="test", color_hex="ff0000")
    assert "format #RRGGBB" in str(exc_info.value)

    # Invalid format - wrong length
    with pytest.raises(ValidationError) as exc_info:
        LabelBase(name="test", color_hex="#ff00")
    assert "format #RRGGBB" in str(exc_info.value)

    # Invalid format - non-hex digits
    with pytest.raises(ValidationError) as exc_info:
        LabelBase(name="test", color_hex="#gggggg")
    assert "hex digits" in str(exc_info.value)

    # Test LabelUpdate with None color (should be allowed)
    update_no_color = LabelUpdate(name="test")
    assert update_no_color.color_hex is None

    # Test LabelUpdate with valid color
    update_with_color = LabelUpdate(color_hex="#00ff00")
    assert update_with_color.color_hex == "#00ff00"

    # Test LabelUpdate with invalid color
    with pytest.raises(ValidationError) as exc_info:
        LabelUpdate(color_hex="invalid")
    assert "format #RRGGBB" in str(exc_info.value)
