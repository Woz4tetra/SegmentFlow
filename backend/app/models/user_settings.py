"""User settings stored by cookie identifier."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Theme(str, Enum):
    """Available UI themes."""

    LIGHT = "light"
    DARK = "dark"


class UserSettings(Base):
    """Persistent per-user (cookie-scoped) settings."""

    __tablename__ = "user_settings"

    cookie_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    theme: Mapped[str] = mapped_column(String(20), default=Theme.LIGHT, nullable=False)
    visible_columns: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    column_order: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserSettings(cookie_id={self.cookie_id}, theme={self.theme})>"
