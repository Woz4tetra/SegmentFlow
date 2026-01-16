"""Mask database model."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.image import Image
    from app.models.label import Label


class Mask(BaseModel):
    """Persisted mask contour for a labeled object."""

    __tablename__ = "masks"

    image_id: Mapped[UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label_id: Mapped[UUID] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # contour_polygon is a list of [x, y] coordinate pairs stored as JSON
    contour_polygon: Mapped[list[list[Any]]] = mapped_column(JSON, nullable=False)
    area: Mapped[float] = mapped_column(Float, nullable=False)

    image: Mapped["Image"] = relationship("Image", back_populates="masks")
    label: Mapped["Label"] = relationship("Label", back_populates="masks")

    def __repr__(self) -> str:
        return (
            f"<Mask(id={self.id}, image_id={self.image_id}, label_id={self.label_id},"
            f" area={self.area})>"
        )
