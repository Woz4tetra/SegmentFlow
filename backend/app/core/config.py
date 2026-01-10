"""Application configuration settings."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Use tomllib for Python 3.11+, otherwise use tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


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


def _load_toml_config() -> Dict[str, Any]:
    """Load configuration from TOML file.
    
    Looks for config.toml in the following locations (in order):
    1. ~/.config/segmentflow/config.toml (Linux/macOS user config directory)
    2. ./config.toml (current working directory)
    3. If not found, returns empty dict
    
    Returns:
        Dictionary of configuration values from TOML file, or empty dict if not found
        
    Raises:
        ValueError: If TOML file exists but cannot be parsed
    """
    if tomllib is None:
        return {}
    
    config_locations = [
        Path.home() / ".config" / "segmentflow" / "config.toml",
        Path("config.toml"),
    ]
    
    for config_path in config_locations:
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    toml_data = tomllib.load(f)
                print(f"✓ Loaded configuration from {config_path}")
                return toml_data
            except (tomllib.TOMLDecodeError, OSError) as e:
                raise ValueError(
                    f"Failed to parse TOML configuration file at {config_path}: {e}"
                ) from e
    
    # No config file found - this is not an error, use defaults
    return {}


def _merge_toml_with_env(toml_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge TOML configuration with environment variables.
    
    Environment variables take precedence over TOML values.
    Also handles nested configuration sections (e.g., [database], [processing]).
    
    Args:
        toml_config: Configuration dictionary loaded from TOML file
        
    Returns:
        Merged configuration dictionary suitable for Settings initialization
    """
    import os
    
    merged = {}
    
    # Flatten nested TOML sections into Settings field names
    # Example: [database] host -> DB_HOST
    if "database" in toml_config:
        db_config = toml_config["database"]
        merged["DB_HOST"] = db_config.get("host", os.getenv("DB_HOST"))
        merged["DB_PORT"] = db_config.get("port", os.getenv("DB_PORT"))
        merged["DB_NAME"] = db_config.get("name", os.getenv("DB_NAME"))
        merged["DB_USER"] = db_config.get("user", os.getenv("DB_USER"))
        merged["DB_PASSWORD"] = db_config.get("password", os.getenv("DB_PASSWORD"))
        merged["DB_PASSWORD_FILE"] = db_config.get("password_file", os.getenv("DB_PASSWORD_FILE"))
        merged["DATABASE_URL"] = db_config.get("url", os.getenv("DATABASE_URL"))
    
    # Processing configuration
    if "processing" in toml_config:
        proc_config = toml_config["processing"]
        merged["MAX_PROPAGATION_LENGTH"] = proc_config.get(
            "max_propagation_length", os.getenv("MAX_PROPAGATION_LENGTH")
        )
        merged["INFERENCE_WIDTH"] = proc_config.get(
            "inference_width", os.getenv("INFERENCE_WIDTH")
        )
        merged["OUTPUT_WIDTH"] = proc_config.get(
            "output_width", os.getenv("OUTPUT_WIDTH")
        )
        merged["MASK_TRANSPARENCY"] = proc_config.get(
            "mask_transparency", os.getenv("MASK_TRANSPARENCY")
        )
        merged["BIG_JUMP_SIZE"] = proc_config.get(
            "big_jump_size", os.getenv("BIG_JUMP_SIZE")
        )
    
    # Storage configuration
    if "storage" in toml_config:
        storage_config = toml_config["storage"]
        merged["PROJECTS_ROOT_DIR"] = storage_config.get(
            "projects_root_dir", os.getenv("PROJECTS_ROOT_DIR")
        )
    
    # SAM configuration
    if "sam" in toml_config:
        sam_config = toml_config["sam"]
        merged["SAM_MODEL_PATH"] = sam_config.get(
            "model_path", os.getenv("SAM_MODEL_PATH")
        )
    
    # Server configuration
    if "server" in toml_config:
        server_config = toml_config["server"]
        merged["DEBUG"] = server_config.get("debug", os.getenv("DEBUG"))
        merged["PROJECT_NAME"] = server_config.get("project_name", os.getenv("PROJECT_NAME"))
        merged["VERSION"] = server_config.get("version", os.getenv("VERSION"))
        merged["API_V1_STR"] = server_config.get("api_v1_str", os.getenv("API_V1_STR"))
        
        if "cors_origins" in server_config:
            merged["CORS_ORIGINS"] = server_config["cors_origins"]
    
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
        print(f"✗ Configuration error: {e}", file=sys.stderr)
        raise
    
    merged_config = _merge_toml_with_env(toml_config)
    
    try:
        return Settings(**merged_config)
    except ValidationError as e:
        print(f"✗ Configuration validation error: {e}", file=sys.stderr)
        raise


try:
    settings = _create_settings()
except (ValueError, ValidationError) as e:
    print(f"Failed to load configuration: {e}", file=sys.stderr)
    sys.exit(1)
