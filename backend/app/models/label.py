"""Label database model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.project import Project


class Label(BaseModel):
    """Label class definition model.

    Attributes:
        project_id: Foreign key to parent project
        name: Label class name
        color_hex: Color in hex format (#RRGGBB)
        thumbnail_path: Optional path to label thumbnail image
        project: Parent project relationship
    """

    __tablename__ = "labels"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)  # #RRGGBB
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="labels")

    def __repr__(self) -> str:
        """Return string representation.

        Returns:
            str: Label representation
        """
        return f"<Label(id={self.id}, name='{self.name}', color='{self.color_hex}')>"
