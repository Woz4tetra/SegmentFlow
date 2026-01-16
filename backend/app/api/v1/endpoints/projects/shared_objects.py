"""Projects endpoint for CRUD operations."""

from fastapi import APIRouter

from app.core.video_upload import VideoUploadService

router = APIRouter()

# Global video upload service instance
upload_service = VideoUploadService()

# In-memory conversion progress tracker: {project_id: {"saved": int, "total": int, "error": bool}}
conversion_progress: dict[str, dict[str, int | bool]] = {}
