"""Label database model."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.labeled_point import LabeledPoint
    from app.models.mask import Mask


class Label(BaseModel):
    """Label class definition model.

    Attributes:
        name: Label class name
        color_hex: Color in hex format (#RRGGBB)
        thumbnail_path: Optional path to label thumbnail image
    """

    __tablename__ = "labels"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)  # #RRGGBB
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    points: Mapped[list["LabeledPoint"]] = relationship(
        "LabeledPoint",
        back_populates="label",
        cascade="all, delete-orphan",
    )
    masks: Mapped[list["Mask"]] = relationship(
        "Mask",
        back_populates="label",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Return string representation.

        Returns:
            str: Label representation
        """
        return f"<Label(id={self.id}, name='{self.name}', color='{self.color_hex}')>"
