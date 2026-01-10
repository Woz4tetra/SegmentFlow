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
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description=(
            "Complete database URL. If not provided, it will be assembled from DB_* settings."
        ),
    )
    DB_HOST: str = Field(default="localhost", description="Database host")
    DB_PORT: int = Field(default=5432, description="Database port")
    DB_NAME: str = Field(default="segmentflow", description="Database name")
    DB_USER: str = Field(default="segmentflow", description="Database user")
    DB_PASSWORD: Optional[str] = Field(default=None, description="Database password")
    DB_PASSWORD_FILE: Optional[str] = Field(
        default=None,
        description="Path to file containing database password (e.g., /run/secrets/postgres_password)",
    )
    
    # CORS configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins for frontend",
    )

    def get_database_url(self) -> str:
        """Return the effective database URL.

        Order of precedence:
        1. Explicit `DATABASE_URL` if provided
        2. Assemble from `DB_*` settings, reading password from `DB_PASSWORD_FILE` when available
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        password = self.DB_PASSWORD
        if self.DB_PASSWORD_FILE:
            try:
                with open(self.DB_PASSWORD_FILE, "r", encoding="utf-8") as f:
                    password = f.read().strip()
            except (FileNotFoundError, OSError, IOError):
                # Fall back to provided DB_PASSWORD or empty
                pass

        if not password:
            # Default to SQLite if no password provided and no DATABASE_URL
            return "sqlite+aiosqlite:///./segmentflow.db"

        return (
            f"postgresql+asyncpg://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
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
