"""Tests for video upload endpoints."""

import hashlib
import io
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


@pytest.fixture
async def test_project(db: AsyncSession, clean_db: AsyncIterator) -> Project:
    """Create a test project for video upload tests.

    Args:
        db: Database session
        clean_db: Clean database fixture

    Yields:
        Project: Created test project
    """
    project = Project(name="Test Video Upload Project")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    yield project
    # Cleanup
    await db.delete(project)
    await db.commit()


def create_mock_video_file(size_mb: int = 10) -> tuple[bytes, str]:
    """Create a mock video file for testing.

    Args:
        size_mb: Size of the mock file in megabytes

    Returns:
        tuple: (file_bytes, sha256_hash)
    """
    # Create mock video data (just zeros, simulating video bytes)
    file_size = size_mb * 1024 * 1024
    file_data = b"\x00" * file_size

    # Compute SHA-256 hash
    hasher = hashlib.sha256()
    hasher.update(file_data)
    file_hash = hasher.hexdigest()

    return file_data, file_hash


@pytest.mark.asyncio
async def test_init_video_upload_success(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test successful upload initialization.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 5,
            "total_size": 50 * 1024 * 1024,  # 50MB
            "file_hash": "12345678" * 8,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == str(test_project.id)
    assert data["total_chunks"] == 5
    assert data["total_size"] == 50 * 1024 * 1024


@pytest.mark.asyncio
async def test_init_video_upload_project_not_found(
    client: AsyncClient,
    clean_db: AsyncIterator,
) -> None:
    """Test upload init with non-existent project.

    Args:
        client: AsyncClient for HTTP requests
        clean_db: Clean database fixture
    """
    fake_id = uuid4()
    response = await client.post(
        f"/api/v1/projects/{fake_id}/upload/init",
        params={
            "total_chunks": 5,
            "total_size": 50 * 1024 * 1024,
            "file_hash": "12345678" * 8,
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_init_video_upload_file_too_large(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test upload init with file exceeding 1GB limit.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 100,
            "total_size": 1024 * 1024 * 1024 + 1,  # 1GB + 1 byte
            "file_hash": "12345678" * 8,
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_chunk_success(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test successful chunk upload.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Initialize upload first
    chunk_size = 10 * 1024 * 1024  # 10MB
    total_chunks = 3
    file_data, file_hash = create_mock_video_file(chunk_size // 1024 // 1024)

    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": total_chunks,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )
    assert init_response.status_code == 200

    # Upload first chunk
    chunk_data = file_data[:chunk_size]
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/chunk",
        params={
            "chunk_number": 0,
        },
        files={"chunk_data": ("chunk_0", io.BytesIO(chunk_data))},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == str(test_project.id)
    assert data["chunks_received"] == 1
    assert data["total_chunks"] == total_chunks
    assert data["status"] == "uploading"


@pytest.mark.asyncio
async def test_upload_chunk_no_session(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test chunk upload without initialized session.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    chunk_data = b"test data"
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/chunk",
        params={
            "chunk_number": 0,
        },
        files={"chunk_data": ("chunk_0", io.BytesIO(chunk_data))},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_upload_progress(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test getting upload progress.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Initialize upload
    chunk_size = 10 * 1024 * 1024  # 10MB
    total_chunks = 3
    file_data, file_hash = create_mock_video_file(chunk_size // 1024 // 1024)

    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": total_chunks,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )
    assert init_response.status_code == 200

    # Upload one chunk
    chunk_data = file_data[:chunk_size]
    await client.post(
        f"/api/v1/projects/{test_project.id}/upload/chunk",
        params={
            "chunk_number": 0,
        },
        files={"chunk_data": ("chunk_0", io.BytesIO(chunk_data))},
    )

    # Get progress
    response = await client.get(
        f"/api/v1/projects/{test_project.id}/upload/progress",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["chunks_received"] == 1
    assert data["total_chunks"] == total_chunks
    assert data["status"] == "uploading"


@pytest.mark.asyncio
async def test_cancel_video_upload(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test cancelling a video upload.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Initialize upload
    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 3,
            "total_size": 30 * 1024 * 1024,
            "file_hash": "12345678" * 8,
        },
    )
    assert init_response.status_code == 200

    # Cancel upload
    response = await client.delete(
        f"/api/v1/projects/{test_project.id}/upload",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == str(test_project.id)


@pytest.mark.asyncio
async def test_complete_video_upload_success(
    client: AsyncClient,
    test_project: Project,
    tmp_path: Path,
    clean_db: AsyncIterator,
) -> None:
    """Test successful completion of chunked video upload.

    This test verifies the full upload workflow: init -> multiple chunks -> complete

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        tmp_path: Temporary directory for test files
        clean_db: Clean database fixture
    """
    # Create small test file to avoid large file in tests
    chunk_size = 1 * 1024 * 1024  # 1MB
    total_chunks = 3
    file_data, file_hash = create_mock_video_file(chunk_size // 1024 // 1024 * total_chunks)

    # Initialize upload
    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": total_chunks,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )
    assert init_response.status_code == 200

    # Upload all chunks
    for i in range(total_chunks):
        start = i * chunk_size
        end = min((i + 1) * chunk_size, len(file_data))
        chunk_data = file_data[start:end]

        response = await client.post(
            f"/api/v1/projects/{test_project.id}/upload/chunk",
            params={
                "chunk_number": i,
            },
            files={"chunk_data": (f"chunk_{i}", io.BytesIO(chunk_data))},
        )
        assert response.status_code == 200

    # Complete upload
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/complete",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == str(test_project.id)
    assert "video_path" in data
    assert data["file_size"] == len(file_data)


@pytest.mark.asyncio
async def test_complete_upload_missing_chunks(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test completing upload with missing chunks.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Initialize upload expecting 3 chunks
    file_data, file_hash = create_mock_video_file(3)

    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 3,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )
    assert init_response.status_code == 200

    # Upload only 1 chunk
    chunk_data = file_data[: 1024 * 1024]
    await client.post(
        f"/api/v1/projects/{test_project.id}/upload/chunk",
        params={
            "chunk_number": 0,
        },
        files={"chunk_data": ("chunk_0", io.BytesIO(chunk_data))},
    )

    # Try to complete with missing chunks
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/complete",
    )

    assert response.status_code == 422  # Unprocessable entity


@pytest.mark.asyncio
async def test_upload_large_file_simulation(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test chunked upload simulating large file (100MB+).

    Uses small chunks to simulate uploading a large file without actually
    using 100MB of memory in the test.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Simulate 100MB file with 10 chunks of 10MB each
    chunk_size = 10 * 1024 * 1024  # 10MB per chunk
    total_chunks = 10
    total_size = chunk_size * total_chunks  # 100MB total

    # Create file data
    file_data = b"\x00" * total_size
    hasher = hashlib.sha256()
    hasher.update(file_data)
    file_hash = hasher.hexdigest()

    # Initialize upload
    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": total_chunks,
            "total_size": total_size,
            "file_hash": file_hash,
        },
    )
    assert init_response.status_code == 200

    # Upload all chunks
    for i in range(total_chunks):
        start = i * chunk_size
        end = (i + 1) * chunk_size
        chunk_data = file_data[start:end]

        response = await client.post(
            f"/api/v1/projects/{test_project.id}/upload/chunk",
            params={
                "chunk_number": i,
            },
            files={"chunk_data": (f"chunk_{i}", io.BytesIO(chunk_data))},
        )
        assert response.status_code == 200

        # Check progress
        progress_response = await client.get(
            f"/api/v1/projects/{test_project.id}/upload/progress",
        )
        assert progress_response.status_code == 200
        progress_data = progress_response.json()
        assert progress_data["chunks_received"] == i + 1


@pytest.mark.asyncio
async def test_complete_upload_invalid_hash(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test completing upload with hash mismatch.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Create file with actual hash
    file_data = b"\x00" * (2 * 1024 * 1024)  # 2MB
    hasher = hashlib.sha256()
    hasher.update(file_data)
    actual_hash = hasher.hexdigest()

    # Use wrong hash for initialization
    wrong_hash = "f" * 64

    init_response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 2,
            "total_size": len(file_data),
            "file_hash": wrong_hash,  # Wrong hash
        },
    )
    assert init_response.status_code == 200

    # Upload chunks
    chunk_size = 1 * 1024 * 1024
    for i in range(2):
        start = i * chunk_size
        end = (i + 1) * chunk_size
        chunk_data = file_data[start:end]

        response = await client.post(
            f"/api/v1/projects/{test_project.id}/upload/chunk",
            params={
                "chunk_number": i,
            },
            files={"chunk_data": (f"chunk_{i}", io.BytesIO(chunk_data))},
        )
        assert response.status_code == 200

    # Complete upload should fail due to hash mismatch
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/complete",
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_multiple_projects_concurrent(
    client: AsyncClient,
    db: AsyncSession,
    clean_db: AsyncIterator,
) -> None:
    """Test uploading to multiple projects simultaneously.

    Args:
        client: AsyncClient for HTTP requests
        db: Database session
        clean_db: Clean database fixture
    """
    # Create two projects
    project1 = Project(name="Project 1")
    project2 = Project(name="Project 2")
    db.add_all([project1, project2])
    await db.commit()
    await db.refresh(project1)
    await db.refresh(project2)

    # Initialize uploads for both
    file_data, file_hash = create_mock_video_file(1)

    for project in [project1, project2]:
        response = await client.post(
            f"/api/v1/projects/{project.id}/upload/init",
            params={
                "total_chunks": 1,
                "total_size": len(file_data),
                "file_hash": file_hash,
            },
        )
        assert response.status_code == 200

    # Upload chunk for project 1
    response1 = await client.post(
        f"/api/v1/projects/{project1.id}/upload/chunk",
        params={
            "chunk_number": 0,
        },
        files={"chunk_data": ("chunk_0", io.BytesIO(file_data))},
    )
    assert response1.status_code == 200

    # Upload chunk for project 2
    response2 = await client.post(
        f"/api/v1/projects/{project2.id}/upload/chunk",
        params={
            "chunk_number": 0,
        },
        files={"chunk_data": ("chunk_0", io.BytesIO(file_data))},
    )
    assert response2.status_code == 200

    # Verify separate progress for each
    progress1 = await client.get(
        f"/api/v1/projects/{project1.id}/upload/progress",
    )
    progress2 = await client.get(
        f"/api/v1/projects/{project2.id}/upload/progress",
    )

    assert progress1.status_code == 200
    assert progress2.status_code == 200
    assert progress1.json()["chunks_received"] == 1
    assert progress2.json()["chunks_received"] == 1


@pytest.mark.asyncio
async def test_init_upload_duplicate_session(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test that initializing upload twice for same project fails.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    file_data, file_hash = create_mock_video_file(1)

    # First init should succeed
    response1 = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 1,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )
    assert response1.status_code == 200

    # Second init should fail with 400
    response2 = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 1,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )
    assert response2.status_code == 400
    assert "already in progress" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_chunk_out_of_range(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test uploading a chunk with invalid chunk number.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    file_data, file_hash = create_mock_video_file(1)

    # Init upload with 2 chunks
    await client.post(
        f"/api/v1/projects/{test_project.id}/upload/init",
        params={
            "total_chunks": 2,
            "total_size": len(file_data),
            "file_hash": file_hash,
        },
    )

    # Try to upload chunk 5 (out of range)
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/chunk",
        params={
            "chunk_number": 5,
        },
        files={"chunk_data": ("chunk_5", io.BytesIO(file_data))},
    )
    assert response.status_code == 400  # Bad request for invalid chunk number


@pytest.mark.asyncio
async def test_complete_upload_no_session(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test completing upload without initializing session.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Try to complete without init
    response = await client.post(
        f"/api/v1/projects/{test_project.id}/upload/complete",
    )
    assert response.status_code == 400  # Bad request for no session


@pytest.mark.asyncio
async def test_get_progress_no_session(
    client: AsyncClient,
    test_project: Project,
    clean_db: AsyncIterator,
) -> None:
    """Test getting progress without initializing session.

    Args:
        client: AsyncClient for HTTP requests
        test_project: Test project fixture
        clean_db: Clean database fixture
    """
    # Try to get progress without init
    response = await client.get(
        f"/api/v1/projects/{test_project.id}/upload/progress",
    )
    assert response.status_code == 404
