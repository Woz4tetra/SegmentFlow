"""Propagation endpoints package.

This package provides API endpoints for label propagation using SAM3:
- POST /projects/{project_id}/propagate - Start a propagation job
- GET /projects/{project_id}/propagate/{job_id} - Get job status
- WS /projects/{project_id}/propagate/{job_id}/ws - Real-time progress updates
"""

from .get_status import get_propagation_status
from .progress_websocket import propagation_progress_websocket
from .shared_objects import router
from .start_propagation import start_propagation

__all__ = [
    "get_propagation_status",
    "propagation_progress_websocket",
    "router",
    "start_propagation",
]
