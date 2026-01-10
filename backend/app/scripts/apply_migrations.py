"""Run database migrations (schema creation) for SegmentFlow.

This script applies the current SQLAlchemy metadata to the configured database.
It is intended to be run via ``python -m app.scripts.apply_migrations``.
"""

from __future__ import annotations

import asyncio

from app.core.database import engine, init_db
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _run() -> None:
    logger.info("Starting migrations...")
    await init_db()
    await engine.dispose()
    logger.info("Migrations completed and engine disposed.")


def main() -> None:
    """Entry point for CLI execution."""

    asyncio.run(_run())


if __name__ == "__main__":
    main()
