"""Test configuration and fixtures."""

import os
from collections.abc import AsyncIterator

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient


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
