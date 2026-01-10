"""Labeled point database model."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.image import Image
    from app.models.label import Label


class LabeledPoint(BaseModel):
    """User-provided point used for SAM prompts."""

    __tablename__ = "labeled_points"

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
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    include: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    image: Mapped["Image"] = relationship("Image", back_populates="points")
    label: Mapped["Label"] = relationship("Label", back_populates="points")

    def __repr__(self) -> str:
        return (
            f"<LabeledPoint(id={self.id}, image_id={self.image_id}, label_id={self.label_id},"
            f" include={self.include})>"
        )
