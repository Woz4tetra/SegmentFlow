"""Database configuration and session management."""

from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import settings


def _is_sqlite(url: str) -> bool:
    """Return True when the configured URL uses SQLite."""
    return url.startswith("sqlite")


class Base(DeclarativeBase):
    """Base class for all database models."""
    
    pass


# Create async engine
db_url = settings.get_database_url()
_use_sqlite = _is_sqlite(db_url)


engine: AsyncEngine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    future=True,
    # StaticPool avoids threading issues for in-process SQLite
    poolclass=StaticPool if _use_sqlite else NullPool,
)


# Enable foreign keys for SQLite
if _use_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign key support in SQLite.
        
        Args:
            dbapi_conn: Database connection
            connection_record: Connection record
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        ```python
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
        ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database by creating all tables.
    
    Called during application startup.
    """
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
