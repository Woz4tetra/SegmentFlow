"""GPU detection and management utilities."""

import pynvml  # type: ignore

from app.core.logging import get_logger

logger = get_logger(__name__)


def get_available_gpu_count() -> int:
    """Detect the number of available GPUs using pynvml.

    Returns:
        Number of available GPUs, or 0 if pynvml cannot detect any or is unavailable.
    """
    try:
        pynvml.nvmlInit()
        device_count: int = pynvml.nvmlDeviceGetCount()
        pynvml.nvmlShutdown()
        logger.info(f"pynvml detected {device_count} GPU(s)")
        return device_count
    except Exception as e:
        logger.warning(f"Failed to detect GPUs with pynvml: {e}")
    return 0
