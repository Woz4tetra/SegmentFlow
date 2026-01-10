"""FastAPI main application entry point."""

import inspect
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Handle application startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None during application runtime
    """
    # Startup: Initialize database
    logger.info("Starting SegmentFlow application")
    await init_db()
    logger.info("Database initialization complete")
    yield
    # Shutdown: Cleanup resources if needed
    logger.info("Shutting down SegmentFlow application")
    # Dispose database engine to ensure background threads are closed
    try:
        dispose_result = engine.dispose()
        if inspect.isawaitable(dispose_result):
            await dispose_result
        logger.info("Database engine disposed")
    except Exception as e:
        logger.warning(f"Error disposing database engine: {e}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
