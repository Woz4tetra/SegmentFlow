"""Test configuration and fixtures."""

import os
from collections.abc import AsyncIterator

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine, get_db
from app.models.image import Image
from app.models.label import Label
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project
from app.models.stats import Stats

# Skip SAM3 initialization during tests for speed
# This must be set BEFORE importing app.main
os.environ["SEGMENTFLOW_SKIP_SAM3"] = "1"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Provide an AsyncClient for testing.

    - Forces SQLite to use NullPool in tests to avoid background threads.
    - Wraps the app in LifespanManager to guarantee startup/shutdown.
    - Ensures ASGITransport closes cleanly to avoid event-loop/thread hangs.
    """
    os.environ.setdefault("SEGMENTFLOW_SQLITE_POOL", "NullPool")

    from app.main import app

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        # Explicitly close transport to trigger FastAPI shutdown and release resources
        await transport.aclose()


@pytest_asyncio.fixture
async def db(clean_db: AsyncIterator) -> AsyncIterator[AsyncSession]:
    """Provide a database session for tests.

    Uses the clean_db fixture to ensure database isolation and provides
    a fresh AsyncSession for each test.

    Args:
        clean_db: Clean database fixture

    Yields:
        AsyncSession: Database session for the test
    """
    async for session in get_db():
        yield session


@pytest_asyncio.fixture
async def clean_db() -> AsyncIterator[None]:
    """Clean database before each test.

    Deletes all data from all tables to ensure test isolation.
    Tables are deleted in dependency order (foreign key constraints first).
    """
    # Get a session to execute deletions
    async with engine.begin() as conn:
        # Delete in reverse order of foreign key dependencies
        await conn.execute(delete(LabeledPoint))
        await conn.execute(delete(Mask))
        await conn.execute(delete(Stats))
        await conn.execute(delete(Image))
        await conn.execute(delete(Label))
        await conn.execute(delete(Project))

    yield

    # Cleanup after test
    async with engine.begin() as conn:
        await conn.execute(delete(LabeledPoint))
        await conn.execute(delete(Mask))
        await conn.execute(delete(Stats))
        await conn.execute(delete(Image))
        await conn.execute(delete(Label))
        await conn.execute(delete(Project))
