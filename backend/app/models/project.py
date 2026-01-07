"""Project database model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.label import Label
    from app.models.image import Image


class ProjectStage(str, Enum):
    """Project stage enum."""
    
    UPLOAD = "upload"
    TRIM = "trim"
    MANUAL_LABELING = "manual_labeling"
    PROPAGATION = "propagation"
    VALIDATION = "validation"
    EXPORT = "export"


class Project(BaseModel):
    """Project model for annotation projects.
    
    Attributes:
        name: Project display name
        video_path: Path to uploaded video file
        trim_start: Start frame for trimmed video (0-indexed)
        trim_end: End frame for trimmed video (0-indexed)
        stage: Current project stage
        locked_by: Client session ID that has locked this project
        active: Whether project is active or archived
        labels: Related label definitions
        images: Related images/frames
    """
    
    __tablename__ = "projects"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    video_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    trim_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trim_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(
        String(50),
        default=ProjectStage.UPLOAD.value,
        nullable=False,
    )
    locked_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    labels: Mapped[list["Label"]] = relationship(
        "Label",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    images: Mapped[list["Image"]] = relationship(
        "Image",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        """Return string representation.
        
        Returns:
            str: Project representation
        """
        return f"<Project(id={self.id}, name='{self.name}', stage='{self.stage}')>"
