"""Annotation statistics database model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.image import Image
    from app.models.project import Project


class Stats(BaseModel):
    """Per-image and per-project timing statistics."""

    __tablename__ = "stats"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    time_spent_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    propagation_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="stats")
    image: Mapped[Image | None] = relationship("Image", back_populates="stats")

    def __repr__(self) -> str:
        return (
            f"<Stats(id={self.id}, project_id={self.project_id}, image_id={self.image_id},"
            f" time_spent_ms={self.time_spent_ms})>"
        )
