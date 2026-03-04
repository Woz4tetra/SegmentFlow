"""Application configuration settings."""

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.core.schema import Config, from_dict

# Setup logging for this module
logger = get_logger(__name__)


@dataclass
class Settings:
    """Unified application settings loaded from TOML."""

    config: Config

    @property
    def PROJECT_NAME(self) -> str:  # noqa: N802
        return self.config.server.project_name

    @property
    def VERSION(self) -> str:  # noqa: N802
        return self.config.server.version

    @property
    def API_V1_STR(self) -> str:  # noqa: N802
        return self.config.server.api_v1_str

    @property
    def DEBUG(self) -> bool:  # noqa: N802
        return self.config.server.debug

    @property
    def CORS_ORIGINS(self) -> list[str]:  # noqa: N802
        return self.config.server.cors_origins

    @property
    def DATABASE_URL(self) -> str | None:  # noqa: N802
        return self.config.database.url

    @property
    def DB_HOST(self) -> str:  # noqa: N802
        return self.config.database.host

    @property
    def DB_PORT(self) -> int:  # noqa: N802
        return self.config.database.port

    @property
    def DB_NAME(self) -> str:  # noqa: N802
        return self.config.database.name

    @property
    def DB_USER(self) -> str:  # noqa: N802
        return self.config.database.user

    @property
    def DB_PASSWORD(self) -> str | None:  # noqa: N802
        return self.config.database.password

    @property
    def DB_PASSWORD_FILE(self) -> str | None:  # noqa: N802
        return self.config.database.password_file

    @property
    def PROJECTS_ROOT_DIR(self) -> str:  # noqa: N802
        return self.config.storage.projects_root_dir

    @property
    def SAM_MAX_NUM_GPUS(self) -> int | None:  # noqa: N802
        return self.config.sam.max_num_gpus

    @property
    def MAX_PROPAGATION_LENGTH(self) -> int:  # noqa: N802
        return self.config.processing.max_propagation_length

    @property
    def INFERENCE_WIDTH(self) -> int:  # noqa: N802
        return self.config.processing.inference_width

    @property
    def OUTPUT_WIDTH(self) -> int:  # noqa: N802
        return self.config.processing.output_width

    @property
    def MASK_TRANSPARENCY(self) -> float:  # noqa: N802
        return self.config.processing.mask_transparency

    @property
    def BIG_JUMP_SIZE(self) -> int:  # noqa: N802
        return self.config.processing.big_jump_size

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
                with open(self.DB_PASSWORD_FILE, encoding="utf-8") as f:
                    password = f.read().strip()
            except OSError:
                # Fall back to provided DB_PASSWORD or empty
                pass

        if not password:
            # Default to SQLite if no password provided and no DATABASE_URL
            return "sqlite+aiosqlite:///./segmentflow.db"

        return f"postgresql+asyncpg://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

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
    module_root = Path(__file__).resolve().parents[2]
    config_locations = [
        module_root / "config.toml",
        Path("config.toml"),
    ]

    for config_path in config_locations:
        if not config_path.exists():
            continue
        try:
            with open(config_path, "rb") as f:
                toml_data = tomllib.load(f)

            # Validate TOML structure using schema
            try:
                config = from_dict(Config, toml_data)
                logger.info(f"Loaded and validated configuration from {config_path}")
                return config
            except Exception as e:
                raise ValueError(f"Configuration validation failed: {e}") from e
        except (tomllib.TOMLDecodeError, OSError) as e:
            raise ValueError(
                f"Failed to parse TOML configuration file at {config_path}: {e}"
            ) from e

    # No config file found - return default configuration
    return Config()


def _create_settings() -> Settings:
    """Create Settings instance with TOML and environment configuration.

    Returns:
        Initialized Settings instance with configuration loaded from TOML,
        environment variables, and defaults

    Raises:
        ValueError: If TOML file exists but cannot be parsed
    """
    try:
        toml_config = _load_toml_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    return Settings(toml_config)


try:
    settings = _create_settings()
except ValueError as e:
    logger.error(f"Failed to load configuration: {e}")
    sys.exit(1)
