"""Configuration schema and validation utilities using dataclasses and dacite."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import List, Type, TypeVar

from dacite import Config as DaciteConfig
from dacite import from_dict as from_dict_dacite

T = TypeVar("T")


def from_dict(cls: Type[T], data: dict) -> T:
    """Convert dictionary to dataclass instance with validation.
    
    Args:
        cls: Target dataclass type
        data: Dictionary of configuration data
        
    Returns:
        Instantiated dataclass with values from dictionary
        
    Raises:
        Exception: If data fails validation or type conversion
    """
    return from_dict_dacite(
        data_class=cls,
        data=data,
        config=DaciteConfig(
            strict=True,
            cast=[Enum],
        ),
    )


def _asdict_factory(data):
    """Factory function to convert dataclass to dict with Enum handling.
    
    Args:
        data: List of (key, value) tuples from asdict
        
    Returns:
        Dictionary with Enum values converted to their string representations
    """
    def convert_value(obj):
        if isinstance(obj, Enum):
            return obj.value
        return obj

    return dict((k, convert_value(v)) for k, v in data)


def to_dict(obj) -> dict:
    """Convert dataclass instance to dictionary.
    
    Args:
        obj: Dataclass instance to convert
        
    Returns:
        Dictionary representation with Enum values converted to strings
    """
    return asdict(obj, dict_factory=_asdict_factory)


@dataclass
class DatabaseConfig:
    """Database configuration.
    
    Attributes:
        host: Database server hostname
        port: Database server port
        name: Database name
        user: Database user
        password: Database password (optional)
        password_file: Path to file containing database password (optional)
        url: Full database URL (overrides other settings if provided)
    """
    host: str = "localhost"
    port: int = 5432
    name: str = "segmentflow"
    user: str = "segmentflow"
    password: str = ''
    password_file: str = ''
    url: str = ''


@dataclass
class ServerConfig:
    """Server configuration.
    
    Attributes:
        project_name: Application name
        version: Application version
        api_v1_str: Base path for API v1 endpoints
        debug: Enable debug mode
        cors_origins: List of allowed CORS origins
    """
    project_name: str = "SegmentFlow"
    version: str = "0.1.0"
    api_v1_str: str = "/api/v1"
    debug: bool = True
    cors_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173"
        ]
    )


@dataclass
class StorageConfig:
    """Storage configuration.
    
    Attributes:
        projects_root_dir: Root directory for project files
    """
    projects_root_dir: str = "./data/projects"


@dataclass
class ProcessingConfig:
    """Processing configuration.
    
    Attributes:
        max_propagation_length: Maximum frames to propagate in one batch
        inference_width: Width for SAM inference images
        output_width: Width for output images
        mask_transparency: Transparency level for mask overlays (0.0-1.0)
        big_jump_size: Number of frames for big jump navigation
    """
    max_propagation_length: int = 1000
    inference_width: int = 1024
    output_width: int = 1920
    mask_transparency: float = 0.5
    big_jump_size: int = 500


@dataclass
class SamConfig:
    """SAM model configuration.
    
    Attributes:
        model_path: Path to SAM model checkpoint (optional, downloads if not specified)
    """
    model_path: str = ''


@dataclass
class Config:
    """Complete application configuration.
    
    Loads from TOML file with validation. Environment variables and
    settings take precedence over TOML values.
    
    Attributes:
        server: Server configuration
        database: Database configuration
        storage: Storage configuration
        processing: Processing configuration
        sam: SAM model configuration
    """
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    sam: SamConfig = field(default_factory=SamConfig)
