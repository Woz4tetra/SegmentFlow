"""Application configuration settings."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import setup_logging
from app.core.schema import Config
from app.core.schema import from_dict

import tomllib

# Setup logging for this module
logger = setup_logging(__name__)    

class Settings(BaseSettings):
    """Application settings.
    
    Loads configuration from:
    1. TOML file (config.toml in config directory or current directory)
    2. Environment variables
    3. Default values
    """
    
    model_config = SettingsConfigDict(
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


def _load_toml_config() -> Config:
    """Load and parse configuration from TOML file with validation.
    
    Looks for config.toml in the following locations (in order):
    1. ~/.config/segmentflow/config.toml (Linux/macOS user config directory)
    2. ./config.toml (current working directory)
    3. If not found, returns default Config
    
    Returns:
        Parsed and validated Config dataclass instance
        
    Raises:
        ValueError: If TOML file exists but cannot be parsed or validated
    """
    config_locations = [
        Path.home() / ".config" / "segmentflow" / "config.toml",
        Path("config.toml"),
    ]
    
    for config_path in config_locations:
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    toml_data = tomllib.load(f)
                
                # Validate TOML structure using schema
                try:
                    config = from_dict(Config, toml_data)
                    logger.info(f"Loaded and validated configuration from {config_path}")
                    return config
                except Exception as e:
                    raise ValueError(
                        f"Configuration validation failed: {e}"
                    ) from e
            except (tomllib.TOMLDecodeError, OSError) as e:
                raise ValueError(
                    f"Failed to parse TOML configuration file at {config_path}: {e}"
                ) from e
    
    # No config file found - return default configuration
    return Config()


def _to_int(value: Any, default: int = 0) -> int:
    """Convert value to integer with fallback default.
    
    Args:
        value: Value to convert (can be int, str, or None)
        default: Default value if conversion fails
        
    Returns:
        Converted integer or default
    """
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float with fallback default.
    
    Args:
        value: Value to convert (can be float, int, str, or None)
        default: Default value if conversion fails
        
    Returns:
        Converted float or default
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _to_bool(value: Any, default: bool = True) -> bool:
    """Convert value to boolean with fallback default.
    
    Args:
        value: Value to convert (can be bool, str, or None)
        default: Default value if conversion fails or value is None
        
    Returns:
        Converted boolean or default
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return default


def _merge_toml_with_env(config_schema: Config) -> Dict[str, Any]:
    """Merge parsed configuration schema with environment variables.
    
    Environment variables take precedence over TOML values.
    Converts validated schema object to Settings dictionary.
    
    Args:
        config_schema: Parsed and validated Config dataclass
        
    Returns:
        Merged configuration dictionary suitable for Settings initialization
    """
    merged = {}
    
    # Database configuration
    merged["DB_HOST"] = config_schema.database.host or os.getenv("DB_HOST") or "localhost"
    merged["DB_PORT"] = config_schema.database.port or _to_int(os.getenv("DB_PORT"), 5432)
    merged["DB_NAME"] = config_schema.database.name or os.getenv("DB_NAME") or "segmentflow"
    merged["DB_USER"] = config_schema.database.user or os.getenv("DB_USER") or "segmentflow"
    merged["DB_PASSWORD"] = config_schema.database.password or os.getenv("DB_PASSWORD")
    merged["DB_PASSWORD_FILE"] = config_schema.database.password_file or os.getenv("DB_PASSWORD_FILE")
    merged["DATABASE_URL"] = config_schema.database.url or os.getenv("DATABASE_URL")
    
    # Processing configuration
    merged["MAX_PROPAGATION_LENGTH"] = config_schema.processing.max_propagation_length or _to_int(os.getenv("MAX_PROPAGATION_LENGTH"), 1000)
    merged["INFERENCE_WIDTH"] = config_schema.processing.inference_width or _to_int(os.getenv("INFERENCE_WIDTH"), 1024)
    merged["OUTPUT_WIDTH"] = config_schema.processing.output_width or _to_int(os.getenv("OUTPUT_WIDTH"), 1920)
    merged["MASK_TRANSPARENCY"] = config_schema.processing.mask_transparency or _to_float(os.getenv("MASK_TRANSPARENCY"), 0.5)
    merged["BIG_JUMP_SIZE"] = config_schema.processing.big_jump_size or _to_int(os.getenv("BIG_JUMP_SIZE"), 500)
    
    # Storage configuration
    merged["PROJECTS_ROOT_DIR"] = config_schema.storage.projects_root_dir or os.getenv("PROJECTS_ROOT_DIR") or "./data/projects"
    
    # SAM configuration
    merged["SAM_MODEL_PATH"] = config_schema.sam.model_path or os.getenv("SAM_MODEL_PATH")
    
    # Server configuration
    merged["DEBUG"] = _to_bool(config_schema.server.debug or os.getenv("DEBUG"), True)
    merged["PROJECT_NAME"] = config_schema.server.project_name or os.getenv("PROJECT_NAME") or "SegmentFlow"
    merged["VERSION"] = config_schema.server.version or os.getenv("VERSION") or "0.1.0"
    merged["API_V1_STR"] = config_schema.server.api_v1_str or os.getenv("API_V1_STR") or "/api/v1"
    merged["CORS_ORIGINS"] = config_schema.server.cors_origins or ["http://localhost:3000", "http://localhost:5173"]
    
    # Remove None values to allow Pydantic to use defaults
    return {k: v for k, v in merged.items() if v is not None}


def _create_settings() -> Settings:
    """Create Settings instance with TOML and environment configuration.
    
    Returns:
        Initialized Settings instance with configuration loaded from TOML,
        environment variables, and defaults
        
    Raises:
        ValueError: If TOML file exists but cannot be parsed
        ValidationError: If configuration values fail Pydantic validation
    """
    try:
        toml_config = _load_toml_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    
    merged_config = _merge_toml_with_env(toml_config)
    
    try:
        return Settings(**merged_config)
    except ValidationError as e:
        logger.error(f"Configuration validation error: {e}")
        raise


try:
    settings = _create_settings()
except (ValueError, ValidationError) as e:
    logger.error(f"Failed to load configuration: {e}")
    sys.exit(1)
