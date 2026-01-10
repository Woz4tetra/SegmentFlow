"""Database configuration and session management."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, Pool, StaticPool

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _is_sqlite(url: str) -> bool:
    """Return True when the configured URL uses SQLite."""
    return url.startswith("sqlite")


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create async engine
db_url = settings.get_database_url()
_use_sqlite = _is_sqlite(db_url)

# Allow tests to override SQLite pool to NullPool to avoid background threads
_sqlite_pool_override = os.getenv("SEGMENTFLOW_SQLITE_POOL")
# Select appropriate pool class with explicit type annotation for mypy
_poolclass: type[Pool]
if _use_sqlite:
    _poolclass = NullPool if _sqlite_pool_override == "NullPool" else StaticPool
else:
    _poolclass = NullPool

engine: AsyncEngine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    future=True,
    poolclass=_poolclass,
)

# Log database configuration after engine is created
db_type = "SQLite" if _use_sqlite else "PostgreSQL"
db_display = db_url if _use_sqlite else (db_url.split("@")[1] if "@" in db_url else db_url)
logger.info(f"Using {db_type} database: {db_display}")


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
    logger.info("Initializing database...")
    try:
        # Import models to ensure all metadata is registered before create_all
        from app import models  # noqa: F401

        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
