"""Application configuration settings."""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.
    
    Loads configuration from environment variables or .env file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # Project metadata
    PROJECT_NAME: str = "SegmentFlow"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Database configuration
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./segmentflow.db",
        description=(
            "Database URL. Example: sqlite+aiosqlite:///./segmentflow.db or "
            "postgresql+asyncpg://user:password@localhost:5432/segmentflow"
        ),
    )
    
    # CORS configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins for frontend",
    )
    
    # Server configuration
    DEBUG: bool = Field(default=True, description="Debug mode")
    
    # File storage
    PROJECTS_ROOT_DIR: str = Field(
        default="./data/projects",
        description="Root directory for project files",
    )
    
    # SAM configuration
    SAM_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="Path to SAM model checkpoint",
    )
    
    # Processing configuration
    MAX_PROPAGATION_LENGTH: int = Field(
        default=1000,
        description="Maximum number of frames to propagate in one batch",
    )
    INFERENCE_WIDTH: int = Field(
        default=1024,
        description="Width for SAM inference images",
    )
    OUTPUT_WIDTH: int = Field(
        default=1920,
        description="Width for output images",
    )
    MASK_TRANSPARENCY: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Transparency level for mask overlays",
    )
    BIG_JUMP_SIZE: int = Field(
        default=500,
        description="Number of frames to jump with 'big jump' navigation",
    )


settings = Settings()
