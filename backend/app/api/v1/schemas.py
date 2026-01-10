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
    trim_start: int | None = Field(None, description="Start frame for trimmed video")
    trim_end: int | None = Field(None, description="End frame for trimmed video")
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
    trim_start: int | None = None
    trim_end: int | None = None
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
