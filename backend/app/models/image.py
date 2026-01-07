"""Image database model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.project import Project


class ImageStatus(str, Enum):
    """Image processing status."""
    
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    """Image validation status."""
    
    NOT_VALIDATED = "not_validated"
    PASSED = "passed"
    FAILED = "failed"


class Image(BaseModel):
    """Image/frame model.
    
    Attributes:
        project_id: Foreign key to parent project
        frame_number: Frame number in video (0-indexed)
        inference_path: Path to inference resolution image
        output_path: Path to output resolution image
        status: Processing status
        manually_labeled: Whether image has manual labels
        validation: Validation status
        project: Parent project relationship
    """
    
    __tablename__ = "images"
    
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    inference_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ImageStatus.PENDING.value,
        nullable=False,
    )
    manually_labeled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation: Mapped[str] = mapped_column(
        String(50),
        default=ValidationStatus.NOT_VALIDATED.value,
        nullable=False,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="images")
    
    def __repr__(self) -> str:
        """Return string representation.
        
        Returns:
            str: Image representation
        """
        return f"<Image(id={self.id}, frame={self.frame_number}, status='{self.status}')>"
