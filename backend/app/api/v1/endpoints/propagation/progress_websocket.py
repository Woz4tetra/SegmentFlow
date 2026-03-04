"""Propagation progress WebSocket endpoint.

Provides the WebSocket endpoint for real-time propagation progress updates.
"""

import asyncio
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

from .shared_objects import (
    job_lock,
    job_websockets,
    propagation_jobs,
    router,
)

__all__ = ["propagation_progress_websocket"]

logger = get_logger(__name__)


@router.websocket("/projects/{project_id}/propagate/{job_id}/ws")
async def propagation_progress_websocket(
    websocket: WebSocket,
    project_id: uuid.UUID,
    job_id: str,
) -> None:
    """WebSocket endpoint for real-time propagation progress updates.

    Args:
        websocket: WebSocket connection
        project_id: UUID of the project
        job_id: Job identifier
    """
    await websocket.accept()
    logger.info(f"Propagation WebSocket connected for job {job_id}")

    # Verify job exists
    if job_id not in propagation_jobs:
        await websocket.send_json({"error": f"Job not found: {job_id}"})
        await websocket.close()
        return

    job = propagation_jobs[job_id]
    if job["project_id"] != project_id:
        await websocket.send_json({"error": f"Job {job_id} not found for project {project_id}"})
        await websocket.close()
        return

    # Register websocket for this job
    async with job_lock:
        if job_id not in job_websockets:
            job_websockets[job_id] = []
        job_websockets[job_id].append(websocket)

    try:
        # Send current status immediately
        if job.get("progress"):
            await websocket.send_json(job["progress"].model_dump(mode="json"))

        # Keep connection open and wait for disconnect
        while True:
            try:
                # Wait for any message (client can send keepalive or close)
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break

    finally:
        # Unregister websocket
        async with job_lock:
            if job_id in job_websockets and websocket in job_websockets[job_id]:
                job_websockets[job_id].remove(websocket)

        logger.info(f"Propagation WebSocket disconnected for job {job_id}")
