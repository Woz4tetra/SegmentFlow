"""FastAPI main application entry point."""

import inspect
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.gpu_utils import get_available_gpu_count
from app.core.logging import get_logger
from app.core.sam3_state import set_trackers
from app.core.sam3_tracker import SAM3Tracker

logger = get_logger(__name__)


def _initialize_sam3() -> tuple[SAM3Tracker | None, dict[int, SAM3Tracker]]:
    """Initialize SAM3 models for all available GPUs.

    Returns:
        Tuple of:
        - Primary tracker instance (GPU 0) or None if failed
        - Dict of all tracker instances by GPU ID
    """
    try:
        logger.info("Initializing SAM3 model...")

        # Determine number of GPUs to use
        if not torch.cuda.is_available():
            logger.warning("CUDA not available. SAM3 inference will run on CPU (much slower).")
            num_gpus = 0
        else:
            # Detect available GPUs via pynvml
            available_gpus = get_available_gpu_count()

            # Apply max limit if configured
            if settings.SAM_MAX_NUM_GPUS is not None:
                num_gpus = min(settings.SAM_MAX_NUM_GPUS, available_gpus)
                logger.info(
                    f"Detected {available_gpus} GPU(s), configured max: {settings.SAM_MAX_NUM_GPUS}, "
                    f"using {num_gpus} GPU(s)"
                )
            else:
                num_gpus = available_gpus
                logger.info(f"Detected {available_gpus} GPU(s), using all")

            logger.info(f"Creating SAM3 trackers for {num_gpus} GPU(s)")

        # Create trackers for all available GPUs
        trackers = {}
        primary_tracker = None

        for gpu_id in range(num_gpus):
            try:
                tracker = SAM3Tracker(
                    gpu_id=gpu_id,
                    inference_width=settings.INFERENCE_WIDTH,
                )
                tracker.load_model()
                trackers[gpu_id] = tracker
                logger.info(f"SAM3 tracker initialized for GPU {gpu_id}")

                # Keep reference to GPU 0 as primary
                if gpu_id == 0:
                    primary_tracker = tracker
            except Exception as e:
                logger.error(f"Failed to initialize SAM3 for GPU {gpu_id}: {e}")
                # Continue with remaining GPUs

        if not trackers:
            logger.warning("No SAM3 trackers initialized successfully")
            return None, {}

        logger.info(f"SAM3 models initialized successfully for {len(trackers)} GPU(s)")
        return primary_tracker, trackers
    except Exception as e:
        logger.error(f"Failed to initialize SAM3: {e}")
        logger.warning("Continuing without SAM3. Inference endpoints will fail.")
        return None, {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Handle application startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None during application runtime
    """
    # Startup: Initialize database and SAM3
    logger.info("Starting SegmentFlow application")
    await init_db()
    logger.info("Database initialization complete")

    # Initialize SAM3 trackers and store in global state
    primary_tracker, all_trackers = _initialize_sam3()
    set_trackers(primary_tracker, all_trackers)

    yield

    # Shutdown: Cleanup resources
    logger.info("Shutting down SegmentFlow application")

    # Cleanup SAM3 trackers
    from app.core.sam3_state import get_all_trackers
    for gpu_id, tracker in get_all_trackers().items():
        try:
            tracker.cleanup()
            logger.info(f"SAM3 tracker for GPU {gpu_id} cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up SAM3 tracker for GPU {gpu_id}: {e}")

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
