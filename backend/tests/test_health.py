"""Test suite for health check endpoint."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient


class TestHealth:
    """Health check endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncIterator[AsyncClient]) -> None:
        """Test that health endpoint returns 200 OK.

        This is a sample test to verify the test infrastructure works.
        """
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
