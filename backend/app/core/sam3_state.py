"""Global state for SAM3 tracker instances.

This module holds the global SAM3 tracker instances to avoid circular imports.
Trackers are initialized in main.py during application startup.
"""

from app.core.sam3_tracker import SAM3Tracker

# Global SAM3 tracker instances - one per available GPU
sam3_tracker: SAM3Tracker | None = None  # Primary instance (GPU 0)
sam3_trackers: dict[int, SAM3Tracker] = {}  # All instances by GPU ID


def set_trackers(primary: SAM3Tracker | None, all_trackers: dict[int, SAM3Tracker]) -> None:
    """Set the global tracker instances.

    Args:
        primary: Primary tracker instance (GPU 0) or None
        all_trackers: Dictionary of all tracker instances by GPU ID
    """
    global sam3_tracker, sam3_trackers
    sam3_tracker = primary
    sam3_trackers = all_trackers


def get_primary_tracker() -> SAM3Tracker | None:
    """Get the primary tracker instance.

    Returns:
        Primary tracker or None if not initialized
    """
    return sam3_tracker


def get_all_trackers() -> dict[int, SAM3Tracker]:
    """Get all tracker instances.

    Returns:
        Dictionary of all tracker instances by GPU ID
    """
    return sam3_trackers
