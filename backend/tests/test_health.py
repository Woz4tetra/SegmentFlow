"""Test suite for health check endpoint."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient


class TestHealth:
    """Health check endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncIterator[AsyncClient]) -> None:
        """Test that health endpoint returns 200 OK with proper structure."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data
        assert data["database"] == "connected"

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncIterator[AsyncClient]) -> None:
        """Test that root endpoint returns welcome message."""
        response = await client.get("/api/v1/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data
        assert data["docs"] == "/docs"
