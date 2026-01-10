"""Test configuration and fixtures."""

import asyncio

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """Provide an AsyncClient for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
