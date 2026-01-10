"""Logging configuration for SegmentFlow backend.

Configures structured logging that outputs to stdout for Docker container capture.
"""

import logging
import sys


def setup_logging(name: str = "segmentflow", level: int = logging.INFO) -> logging.Logger:
    """Configure logging for the application.
    
    Sets up a logger that outputs to stdout with a clean format suitable for
    container environments (Docker, Kubernetes, etc.).
    
    Args:
        name: Logger name (typically __name__ of the module)
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter with timestamp, level, and message
    formatter = logging.Formatter(
        "%(levelname)s [%(asctime)s][%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create a configured logger instance.
    
    Ensures the returned logger has the same configuration as produced by
    setup_logging(). If the logger has not yet been configured (no handlers),
    it will be configured via setup_logging; otherwise, the existing
    configuration is preserved.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    # If no handlers are attached, configure this logger
    if not logger.handlers:
        return setup_logging(name=name)
    return logger
