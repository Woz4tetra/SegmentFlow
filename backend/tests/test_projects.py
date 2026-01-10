"""Test suite for project CRUD endpoints."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestProjectCreate:
    """Tests for POST /projects endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_success(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test successful project creation.

        Verifies that a valid project creation request returns 201 with the
        created project details.
        """
        payload = {
            "name": "Test Project",
            "active": True,
        }
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Test Project"
        assert data["active"] is True
        assert data["stage"] == "upload"  # Default stage
        assert data["id"] is not None
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert data["video_path"] is None
        assert data["trim_start"] is None
        assert data["trim_end"] is None
        assert data["locked_by"] is None

    @pytest.mark.asyncio
    async def test_create_project_minimal(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test project creation with minimal required fields.

        Verifies that only a name is required and defaults are applied.
        """
        payload = {"name": "Minimal Project"}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Minimal Project"
        assert data["active"] is True  # Default

    @pytest.mark.asyncio
    async def test_create_project_empty_name(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test project creation with empty name fails.

        Verifies validation of required fields.
        """
        payload = {"name": "", "active": True}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_project_missing_name(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test project creation without name fails.

        Verifies that name is a required field.
        """
        payload = {"active": True}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 422  # Validation error


class TestProjectList:
    """Tests for GET /projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test listing projects when none exist.

        Verifies that an empty list is returned with correct structure.
        """
        response = await client.get("/api/v1/projects")
        assert response.status_code == 200

        data = response.json()
        assert data["projects"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_projects_multiple(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test listing multiple projects.

        Verifies that all created projects are returned in the list.
        They should be in reverse order of creation (most recently updated first),
        though in practice they may have the same timestamp due to fast execution.
        """
        # Create first project
        payload1 = {"name": "Project 1"}
        response1 = await client.post("/api/v1/projects", json=payload1)
        assert response1.status_code == 201
        project1_id = response1.json()["id"]

        # Create second project
        payload2 = {"name": "Project 2"}
        response2 = await client.post("/api/v1/projects", json=payload2)
        assert response2.status_code == 201
        project2_id = response2.json()["id"]

        # List projects
        response = await client.get("/api/v1/projects")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert len(data["projects"]) == 2
        # Both projects should be in the list
        project_ids = {p["id"] for p in data["projects"]}
        assert project1_id in project_ids
        assert project2_id in project_ids

    @pytest.mark.asyncio
    async def test_list_projects_structure(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test that listed projects have correct structure.

        Verifies all required fields are present in the response.
        """
        # Create a project
        payload = {"name": "Structure Test", "active": False}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201

        # List projects
        response = await client.get("/api/v1/projects")
        assert response.status_code == 200

        data = response.json()
        project = data["projects"][0]

        # Check all fields are present
        assert "id" in project
        assert "name" in project
        assert "active" in project
        assert "video_path" in project
        assert "trim_start" in project
        assert "trim_end" in project
        assert "stage" in project
        assert "locked_by" in project
        assert "created_at" in project
        assert "updated_at" in project


class TestProjectGet:
    """Tests for GET /projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_success(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test successfully retrieving a project by ID.

        Verifies all project fields are returned correctly.
        """
        # Create a project
        payload = {"name": "Get Test", "active": True}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Get the project
        response = await client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Get Test"
        assert data["active"] is True
        assert data["stage"] == "upload"

    @pytest.mark.asyncio
    async def test_get_project_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test getting a non-existent project returns 404.

        Verifies proper error handling for missing resources.
        """
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/projects/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_invalid_id(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test getting a project with invalid ID format returns 422.

        Verifies validation of UUID format.
        """
        response = await client.get("/api/v1/projects/not-a-uuid")
        assert response.status_code == 422


class TestProjectUpdate:
    """Tests for PATCH /projects/{project_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_name(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating project name.

        Verifies that a single field can be updated without affecting others.
        """
        # Create a project
        payload = {"name": "Original Name", "active": True}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Update the name
        update_payload = {"name": "Updated Name"}
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["active"] is True  # Unchanged
        assert data["id"] == project_id

    @pytest.mark.asyncio
    async def test_update_project_stage(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating project stage.

        Verifies that stage can be updated to a valid value.
        """
        # Create a project
        payload = {"name": "Stage Test"}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Update the stage
        update_payload = {"stage": "trim"}
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["stage"] == "trim"

    @pytest.mark.asyncio
    async def test_update_project_multiple_fields(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating multiple fields at once.

        Verifies that multiple fields can be updated in a single request.
        """
        # Create a project
        payload = {"name": "Multi Test", "active": True}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Update multiple fields
        update_payload = {
            "name": "New Name",
            "active": False,
            "stage": "manual_labeling",
            "video_path": "/path/to/video.mp4",
            "trim_start": 0,
            "trim_end": 100,
        }
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "New Name"
        assert data["active"] is False
        assert data["stage"] == "manual_labeling"
        assert data["video_path"] == "/path/to/video.mp4"
        assert data["trim_start"] == 0
        assert data["trim_end"] == 100

    @pytest.mark.asyncio
    async def test_update_project_not_found(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating a non-existent project returns 404.

        Verifies proper error handling when updating missing resources.
        """
        fake_id = str(uuid4())
        update_payload = {"name": "New Name"}
        response = await client.patch(
            f"/api/v1/projects/{fake_id}",
            json=update_payload,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project_invalid_stage(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating project with invalid stage returns 422.

        Verifies validation of stage values.
        """
        # Create a project
        payload = {"name": "Invalid Stage Test"}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Update with invalid stage
        update_payload = {"stage": "invalid_stage"}
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_project_empty_name(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating project with empty name returns 422.

        Verifies validation of field constraints.
        """
        # Create a project
        payload = {"name": "Valid Name"}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # Update with empty name
        update_payload = {"name": ""}
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_project_no_changes(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test updating project with no changes succeeds.

        Verifies that an empty update payload is handled gracefully.
        """
        # Create a project
        payload = {"name": "No Change Test", "active": True}
        response = await client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        project_id = response.json()["id"]
        original_updated_at = response.json()["updated_at"]

        # Update with empty payload
        update_payload = {}
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "No Change Test"
        assert data["active"] is True


class TestProjectIntegration:
    """Integration tests for project CRUD operations."""

    @pytest.mark.asyncio
    async def test_project_lifecycle(
        self,
        client: AsyncIterator[AsyncClient],
        clean_db: AsyncIterator[None],
    ) -> None:
        """Test complete project lifecycle: create, get, list, update.

        Verifies that all operations work together correctly.
        """
        # 1. Create a project
        create_payload = {"name": "Lifecycle Project"}
        response = await client.post("/api/v1/projects", json=create_payload)
        assert response.status_code == 201
        project_id = response.json()["id"]

        # 2. Get the project
        response = await client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Lifecycle Project"

        # 3. List projects (should include the new one)
        response = await client.get("/api/v1/projects")
        assert response.status_code == 200
        assert response.json()["total"] >= 1
        project_ids = [p["id"] for p in response.json()["projects"]]
        assert project_id in project_ids

        # 4. Update the project
        update_payload = {
            "name": "Updated Lifecycle Project",
            "stage": "trim",
            "video_path": "/videos/test.mp4",
        }
        response = await client.patch(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["name"] == "Updated Lifecycle Project"
        assert updated["stage"] == "trim"
        assert updated["video_path"] == "/videos/test.mp4"

        # 5. Get again to verify persistence
        response = await client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        final = response.json()
        assert final["name"] == "Updated Lifecycle Project"
        assert final["stage"] == "trim"
        assert final["video_path"] == "/videos/test.mp4"
