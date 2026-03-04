"""Project label enable/disable settings."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.label import Label
    from app.models.project import Project


class ProjectLabelSetting(BaseModel):
    """Per-project label enable/disable settings."""

    __tablename__ = "project_label_settings"
    __table_args__ = (
        UniqueConstraint("project_id", "label_id", name="uq_project_label_setting"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label_id: Mapped[UUID] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional relationships for eager access
    project: Mapped["Project"] = relationship("Project")
    label: Mapped["Label"] = relationship("Label")

    def __repr__(self) -> str:
        return (
            f"<ProjectLabelSetting(project_id={self.project_id}, "
            f"label_id={self.label_id}, enabled={self.enabled})>"
        )
