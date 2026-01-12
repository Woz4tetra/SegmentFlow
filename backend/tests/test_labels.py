"""Test suite for label CRUD endpoints."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestLabelCreate:
    """Tests for POST /projects/{id}/labels endpoint."""

    @pytest.mark.asyncio
    async def test_create_label_success(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        # Create a global label
        label_payload = {
            "name": "Person",
            "color_hex": "#00FF00",
        }
        resp = await client.post(
            "/api/v1/labels",
            json=label_payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Person"
        assert data["color_hex"] == "#00FF00"
        assert data["thumbnail_path"] is None

    @pytest.mark.asyncio
    async def test_create_label_invalid_color(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        # Invalid color format
        resp = await client.post(
            "/api/v1/labels",
            json={"name": "Car", "color_hex": "00FF00"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_label_with_thumbnail(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test creating label with thumbnail path."""
        # Create global label with thumbnail
        label_payload = {
            "name": "Person",
            "color_hex": "#00FF00",
            "thumbnail_path": "/path/to/thumb.png",
        }
        resp = await client.post(
            "/api/v1/labels",
            json=label_payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Person"
        assert data["thumbnail_path"] == "/path/to/thumb.png"

    @pytest.mark.asyncio
    async def test_create_label_empty_name(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test creating label with empty name fails validation."""
        # Empty name should fail
        resp = await client.post(
            "/api/v1/labels",
            json={"name": "", "color_hex": "#00FF00"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_label_missing_required_fields(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test creating label without required fields fails."""
        # Missing name
        resp = await client.post(
            "/api/v1/labels",
            json={"color_hex": "#00FF00"},
        )
        assert resp.status_code == 422

        # Missing color_hex
        resp = await client.post(
            "/api/v1/labels",
            json={"name": "Person"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_multiple_labels(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test creating multiple global labels."""
        # Create first label
        resp1 = await client.post(
            "/api/v1/labels",
            json={"name": "Person", "color_hex": "#00FF00"},
        )
        assert resp1.status_code == 201

        # Create second label
        resp2 = await client.post(
            "/api/v1/labels",
            json={"name": "Car", "color_hex": "#FF0000"},
        )
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]


class TestLabelUpdate:
    """Tests for PATCH /labels/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_label_name_and_color(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        # Create global label
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Car", "color_hex": "#FF0000"},
        )
        label_id = lab.json()["id"]

        # Update
        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={"name": "Vehicle", "color_hex": "#00FFFF"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Vehicle"
        assert data["color_hex"] == "#00FFFF"

    @pytest.mark.asyncio
    async def test_update_label_name_only(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating only the name field."""
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Car", "color_hex": "#FF0000"},
        )
        label_id = lab.json()["id"]
        original_color = lab.json()["color_hex"]

        # Update only name
        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={"name": "Vehicle"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Vehicle"
        assert data["color_hex"] == original_color  # Should be unchanged

    @pytest.mark.asyncio
    async def test_update_label_color_only(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating only the color field."""
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Car", "color_hex": "#FF0000"},
        )
        label_id = lab.json()["id"]
        original_name = lab.json()["name"]

        # Update only color
        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={"color_hex": "#00FFFF"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == original_name  # Should be unchanged
        assert data["color_hex"] == "#00FFFF"

    @pytest.mark.asyncio
    async def test_update_label_thumbnail(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Dog", "color_hex": "#0000FF"},
        )
        label_id = lab.json()["id"]

        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={"thumbnail_path": "/thumbs/dog.png"},
        )
        assert resp.status_code == 200
        assert resp.json()["thumbnail_path"] == "/thumbs/dog.png"

    @pytest.mark.asyncio
    async def test_update_label_invalid_color(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Cat", "color_hex": "#00FF00"},
        )
        label_id = lab.json()["id"]

        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={"color_hex": "00FF00"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_label_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        fake_label = str(uuid4())
        resp = await client.patch(
            f"/api/v1/labels/{fake_label}",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_label_empty_name(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating label with empty name fails validation."""
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Cat", "color_hex": "#00FF00"},
        )
        label_id = lab.json()["id"]

        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={"name": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_label_with_all_fields(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating all label fields at once."""
        lab = await client.post(
            "/api/v1/labels",
            json={"name": "Cat", "color_hex": "#00FF00"},
        )
        label_id = lab.json()["id"]

        resp = await client.patch(
            f"/api/v1/labels/{label_id}",
            json={
                "name": "Dog",
                "color_hex": "#0000FF",
                "thumbnail_path": "/new/path.png",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dog"
        assert data["color_hex"] == "#0000FF"
        assert data["thumbnail_path"] == "/new/path.png"

    @pytest.mark.asyncio
    async def test_update_label_invalid_uuid(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating label with invalid UUID format."""
        resp = await client.patch(
            "/api/v1/labels/not-a-uuid",
            json={"name": "Test"},
        )
        assert resp.status_code == 422
