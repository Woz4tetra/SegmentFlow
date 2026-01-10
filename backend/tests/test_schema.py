"""Database schema creation tests for DATA-001."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

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

            assert _has_fk("labels", "project_id", "projects")
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
        bad_label = Label(project_id=uuid4(), name="orphan", color_hex="#ff0000")

        session.add(bad_label)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_removes_children() -> None:
    """Deleting a project cascades to related labels, images, points, masks, stats."""

    async with AsyncSessionLocal() as session:
        project = Project(name="test-project")
        label = Label(name="person", color_hex="#00ff00", project=project)
        image = Image(project=project, frame_number=1, inference_path="/tmp/i.jpg")
        point = LabeledPoint(image=image, label=label, x=0.5, y=0.6, include=True)
        mask = Mask(image=image, label=label, contour_polygon={"points": []}, area=1.0)
        stats = Stats(project=project, image=image, time_spent_ms=10, propagation_time_ms=0)

        session.add_all([project, label, image, point, mask, stats])
        await session.commit()

        await session.delete(project)
        await session.commit()

    async with AsyncSessionLocal() as session:
        for model in (Project, Label, Image, LabeledPoint, Mask, Stats):
            count = await session.scalar(select(func.count()).select_from(model))
            assert count == 0
