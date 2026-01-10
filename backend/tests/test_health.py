"""Test suite for health check endpoint."""

import pytest


class TestHealth:
    """Health check endpoint tests."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test that health endpoint returns 200 OK.

        This is a sample test to verify the test infrastructure works.
        """
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    def test_sample_unit_test(self):
        """Sample unit test to verify pytest configuration.

        Remove this test once real tests are added.
        """
        assert 1 + 1 == 2
        assert "hello".upper() == "HELLO"
