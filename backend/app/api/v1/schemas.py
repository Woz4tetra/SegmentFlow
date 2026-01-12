"""Pydantic request/response schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProjectBase(BaseModel):
    """Base schema for Project with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    active: bool = Field(default=True, description="Whether project is active")


class ProjectCreate(ProjectBase):
    """Schema for creating a new project.

    Attributes:
        name: Project display name
        active: Whether project is active (optional, defaults to True)
    """

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project.

    Attributes:
        name: Project display name (optional)
        stage: Current project stage (optional)
        trim_start: Start frame for trimmed video (optional)
        trim_end: End frame for trimmed video (optional)
        video_path: Path to uploaded video file (optional)
        locked_by: Client session ID that has locked this project (optional)
        active: Whether project is active (optional)
    """

    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    stage: str | None = Field(None, description="Current project stage")
    trim_start: float | None = Field(None, description="Start time for trimmed video in seconds")
    trim_end: float | None = Field(None, description="End time for trimmed video in seconds")
    video_path: str | None = Field(None, description="Path to uploaded video file")
    locked_by: str | None = Field(
        None,
        description="Client session ID that has locked this project",
    )
    active: bool | None = Field(None, description="Whether project is active")

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str | None) -> str | None:
        """Validate stage value is one of allowed values.

        Args:
            v: Stage value to validate

        Returns:
            str | None: The validated stage value

        Raises:
            ValueError: If stage is not a valid stage value
        """
        if v is not None:
            valid_stages = {
                "upload",
                "trim",
                "manual_labeling",
                "propagation",
                "validation",
                "export",
            }
            if v not in valid_stages:
                msg = f"Invalid stage: {v}. Must be one of {valid_stages}"
                raise ValueError(msg)
        return v


class ProjectResponse(ProjectBase):
    """Schema for project response.

    Attributes:
        id: Unique project identifier
        video_path: Path to uploaded video file
        trim_start: Start frame for trimmed video
        trim_end: End frame for trimmed video
        stage: Current project stage
        locked_by: Client session ID that has locked this project
        created_at: Timestamp when project was created
        updated_at: Timestamp when project was last updated
    """

    id: UUID
    video_path: str | None = None
    trim_start: float | None = None
    trim_end: float | None = None
    stage: str
    locked_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Schema for listing projects.

    Attributes:
        projects: List of project responses
        total: Total number of projects
    """

    projects: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")


# ===== Label Schemas =====


class LabelBase(BaseModel):
    """Base schema for Label with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Label name")
    color_hex: str = Field(..., description="Color in #RRGGBB format")
    thumbnail_path: str | None = Field(default=None, description="Optional path to label thumbnail")

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, v: str) -> str:
        """Validate color hex is in #RRGGBB format."""
        if not isinstance(v, str):
            raise ValueError("color_hex must be a string")
        if len(v) != 7 or not v.startswith("#"):
            raise ValueError("color_hex must be in format #RRGGBB")
        hex_part = v[1:]
        try:
            int(hex_part, 16)
        except ValueError as e:
            raise ValueError("color_hex must contain valid hex digits") from e
        return v


class LabelCreate(LabelBase):
    """Schema for creating a new label."""

    pass


class LabelUpdate(BaseModel):
    """Schema for updating an existing label (partial)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    color_hex: str | None = Field(None, description="Color in #RRGGBB format")
    thumbnail_path: str | None = Field(None, description="Path to thumbnail image")

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex_optional(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 7 or not v.startswith("#"):
            raise ValueError("color_hex must be in format #RRGGBB")
        try:
            int(v[1:], 16)
        except ValueError as e:
            raise ValueError("color_hex must contain valid hex digits") from e
        return v


class LabelResponse(LabelBase):
    """Schema for label response."""

    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ===== Video Upload Schemas =====


class VideoUploadChunkRequest(BaseModel):
    """Schema for uploading a video chunk.

    Attributes:
        chunk_number: Sequential chunk number (0-indexed)
        total_chunks: Total number of chunks in this upload
        chunk_size: Size of this chunk in bytes
        file_hash: SHA-256 hash of complete file for integrity verification
    """

    chunk_number: int = Field(..., ge=0, description="Sequential chunk number (0-indexed)")
    total_chunks: int = Field(..., gt=0, description="Total number of chunks")
    chunk_size: int = Field(..., gt=0, description="Size of this chunk in bytes")
    file_hash: str = Field(
        ..., min_length=64, max_length=64, description="SHA-256 hash of complete file"
    )


class VideoUploadProgressResponse(BaseModel):
    """Schema for video upload progress.

    Attributes:
        project_id: ID of the project
        total_size: Total size of the video file in bytes
        uploaded_size: Number of bytes uploaded so far
        progress_percent: Upload progress as percentage (0-100)
        chunks_received: Number of chunks received so far
        total_chunks: Total number of chunks expected
        status: Current upload status (uploading, completed, failed)
    """

    project_id: UUID
    total_size: int = Field(..., ge=0, description="Total size in bytes")
    uploaded_size: int = Field(..., ge=0, description="Bytes uploaded so far")
    progress_percent: float = Field(..., ge=0, le=100, description="Progress percentage")
    chunks_received: int = Field(..., ge=0, description="Number of chunks received")
    total_chunks: int = Field(..., gt=0, description="Total number of chunks")
    status: str = Field(..., description="Upload status: uploading, completed, or failed")


class VideoUploadCompleteResponse(BaseModel):
    """Schema for completed video upload response.

    Attributes:
        project_id: ID of the project
        video_path: Path where the video was saved
        file_size: Size of uploaded file in bytes
        message: Confirmation message
    """

    project_id: UUID
    video_path: str = Field(..., description="Path where video was saved")
    file_size: int = Field(..., ge=0, description="Size of uploaded file")
    message: str = Field(..., description="Confirmation message")
