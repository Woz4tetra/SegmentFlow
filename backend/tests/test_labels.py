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
        # First create a project
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Labels Project"},
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        # Create a label
        label_payload = {
            "name": "Person",
            "color_hex": "#00FF00",
        }
        resp = await client.post(
            f"/api/v1/projects/{project_id}/labels",
            json=label_payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Person"
        assert data["color_hex"] == "#00FF00"
        assert data["project_id"] == project_id
        assert data["thumbnail_path"] is None

    @pytest.mark.asyncio
    async def test_create_label_invalid_color(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": "Labels Project"},
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        # Invalid color format
        resp = await client.post(
            f"/api/v1/projects/{project_id}/labels",
            json={"name": "Car", "color_hex": "00FF00"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_label_project_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        fake_project = str(uuid4())
        resp = await client.post(
            f"/api/v1/projects/{fake_project}/labels",
            json={"name": "Tree", "color_hex": "#00AA00"},
        )
        assert resp.status_code == 404


class TestLabelUpdate:
    """Tests for PATCH /labels/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_label_name_and_color(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        # Create project and label
        proj = await client.post("/api/v1/projects", json={"name": "Proj"})
        project_id = proj.json()["id"]
        lab = await client.post(
            f"/api/v1/projects/{project_id}/labels",
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
    async def test_update_label_thumbnail(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        proj = await client.post("/api/v1/projects", json={"name": "Proj"})
        project_id = proj.json()["id"]
        lab = await client.post(
            f"/api/v1/projects/{project_id}/labels",
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
        proj = await client.post("/api/v1/projects", json={"name": "Proj"})
        project_id = proj.json()["id"]
        lab = await client.post(
            f"/api/v1/projects/{project_id}/labels",
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
