"""SAM3 model status and inference endpoints."""

import asyncio
import contextlib
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SAMMaskResponse, SAMPointRequest, SAMQueueStatusResponse
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.sam3_state import get_all_trackers, get_primary_tracker
from app.models.image import Image
from app.models.project import Project

logger = get_logger(__name__)

router = APIRouter()


# Global request queue for SAM inference
_sam_request_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
_processing_lock = asyncio.Lock()
_is_processing = False
_background_tasks: set[asyncio.Task] = set()  # Track background tasks


@router.get("/sam3/status", response_model=dict[str, Any])
async def sam3_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get SAM3 model status.

    Returns information about all SAM3 model instances including:
    - Whether models are loaded
    - Which GPUs are in use
    - Inference width configuration
    - Total number of available trackers for parallel propagation

    Args:
        db: Database session dependency

    Returns:
        dict: SAM3 status information

    Example response:
        {
            "initialized": true,
            "primary_gpu_id": 0,
            "num_trackers": 3,
            "available_gpus": [0, 1, 2],
            "trackers": [
                {
                    "gpu_id": 0,
                    "loaded": true,
                    "device": "cuda:0"
                },
                ...
            ],
            "inference_width": 960,
            "cuda_available": true
        }
    """
    sam3_tracker = get_primary_tracker()
    sam3_trackers = get_all_trackers()

    if not sam3_trackers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SAM3 models not initialized. Check server logs for details.",
        )

    # Get info for each tracker
    trackers_info = [
        {
            "gpu_id": tracker.gpu_id,
            "loaded": tracker.model is not None,
            "device": str(tracker.device),
        }
        for tracker in sam3_trackers.values()
    ]

    return {
        "initialized": True,
        "primary_gpu_id": sam3_tracker.gpu_id if sam3_tracker else None,
        "num_trackers": len(sam3_trackers),
        "available_gpus": sorted(sam3_trackers.keys()),
        "trackers": trackers_info,
        "inference_width": settings.INFERENCE_WIDTH,
        "cuda_available": torch.cuda.is_available() if sam3_tracker else False,
    }


def _encode_mask_rle(mask: np.ndarray) -> str:
    """Encode binary mask as run-length encoding string for efficient transmission.

    Args:
        mask: Binary mask array (2D)

    Returns:
        str: RLE encoded string in format "start1,length1,start2,length2,..."
    """
    # Flatten mask to 1D
    flat = mask.flatten()

    # Find run starts and lengths
    diff = np.diff(np.concatenate([[0], flat, [0]]))
    run_starts = np.where(diff == 1)[0]
    run_ends = np.where(diff == -1)[0]
    run_lengths = run_ends - run_starts

    # Encode as comma-separated string
    rle_pairs = []
    for start, length in zip(run_starts, run_lengths, strict=False):
        rle_pairs.append(f"{start},{length}")

    return ";".join(rle_pairs)


def _get_mask_bbox(mask: np.ndarray) -> list[int]:
    """Get bounding box for mask in [x, y, width, height] format.

    Args:
        mask: Binary mask array (2D)

    Returns:
        list[int]: Bounding box [x, y, width, height] or [0, 0, 0, 0] if empty
    """
    # Find non-zero pixels
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not rows.any() or not cols.any():
        return [0, 0, 0, 0]

    y_min, y_max = np.where(rows)[0][[0, -1]]
    x_min, x_max = np.where(cols)[0][[0, -1]]

    return [int(x_min), int(y_min), int(x_max - x_min + 1), int(y_max - y_min + 1)]


async def _process_sam_request(
    request: SAMPointRequest,
    db: AsyncSession,
) -> SAMMaskResponse:
    """Process a single SAM inference request.

    Args:
        request: Point-based mask inference request
        db: Database session

    Returns:
        SAMMaskResponse: Mask inference result

    Raises:
        ValueError: If project or image not found
    """
    start_time = time.perf_counter()

    try:
        # Get primary SAM3 tracker
        tracker = get_primary_tracker()
        if tracker is None:
            return SAMMaskResponse(
                project_id=request.project_id,
                frame_number=request.frame_number,
                label_id=request.label_id,
                mask_rle=None,
                mask_bbox=None,
                request_id=request.request_id,
                inference_time_ms=0.0,
                status="error",
                error="SAM3 model not initialized",
            )

        # Ensure model is loaded before use
        if tracker.model is None or tracker.predictor is None:
            logger.warning("SAM3 model not loaded, attempting to load now...")
            try:
                tracker.load_model()
            except Exception as e:
                logger.error(f"Failed to load SAM3 model: {e}", exc_info=True)
                return SAMMaskResponse(
                    project_id=request.project_id,
                    frame_number=request.frame_number,
                    label_id=request.label_id,
                    mask_rle=None,
                    mask_bbox=None,
                    request_id=request.request_id,
                    inference_time_ms=0.0,
                    status="error",
                    error=f"SAM3 model failed to load: {e}",
                )

        # Verify project exists
        project_result = await db.execute(select(Project).where(Project.id == request.project_id))
        project = project_result.scalar_one_or_none()
        if project is None:
            return SAMMaskResponse(
                project_id=request.project_id,
                frame_number=request.frame_number,
                label_id=request.label_id,
                mask_rle=None,
                mask_bbox=None,
                request_id=request.request_id,
                inference_time_ms=0.0,
                status="error",
                error=f"Project not found: {request.project_id}",
            )

        # Get image for this frame
        image_result = await db.execute(
            select(Image).where(
                Image.project_id == request.project_id,
                Image.frame_number == request.frame_number,
            )
        )
        image = image_result.scalar_one_or_none()
        if image is None:
            return SAMMaskResponse(
                project_id=request.project_id,
                frame_number=request.frame_number,
                label_id=request.label_id,
                mask_rle=None,
                mask_bbox=None,
                request_id=request.request_id,
                inference_time_ms=0.0,
                status="error",
                error=f"Image not found for frame {request.frame_number}",
            )

        # Get inference images directory
        project_dir = Path(settings.PROJECTS_ROOT_DIR) / str(project.id)
        inference_dir = project_dir / "inference"
        if not inference_dir.exists():
            return SAMMaskResponse(
                project_id=request.project_id,
                frame_number=request.frame_number,
                label_id=request.label_id,
                mask_rle=None,
                mask_bbox=None,
                request_id=request.request_id,
                inference_time_ms=0.0,
                status="error",
                error=f"Inference directory not found: {inference_dir}",
            )

        # Set images directory for tracker
        tracker.set_images_dir(str(inference_dir))

        # Convert points and labels to numpy arrays
        points_array = np.array(request.points, dtype=np.float32)
        labels_array = np.array(request.labels, dtype=np.int32)

        # Run inference in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        mask = await loop.run_in_executor(
            None,
            tracker.get_preview_mask,
            request.frame_number,
            hash(str(request.label_id)),  # Use hash of label_id as obj_id
            points_array,
            labels_array,
        )

        if mask is None:
            return SAMMaskResponse(
                project_id=request.project_id,
                frame_number=request.frame_number,
                label_id=request.label_id,
                mask_rle=None,
                mask_bbox=None,
                request_id=request.request_id,
                inference_time_ms=(time.perf_counter() - start_time) * 1000,
                status="error",
                error="Failed to generate mask",
            )

        # Encode mask for transmission
        mask_rle = _encode_mask_rle(mask)
        mask_bbox = _get_mask_bbox(mask)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            f"SAM inference completed in {inference_time_ms:.2f}ms for "
            f"project {request.project_id}, frame {request.frame_number}"
        )

        return SAMMaskResponse(
            project_id=request.project_id,
            frame_number=request.frame_number,
            label_id=request.label_id,
            mask_rle=mask_rle,
            mask_bbox=mask_bbox,
            request_id=request.request_id,
            inference_time_ms=inference_time_ms,
            status="success",
            error="",
        )

    except Exception as e:
        logger.error(f"Error processing SAM request: {e}", exc_info=True)
        return SAMMaskResponse(
            project_id=request.project_id,
            frame_number=request.frame_number,
            label_id=request.label_id,
            mask_rle=None,
            mask_bbox=None,
            request_id=request.request_id,
            inference_time_ms=(time.perf_counter() - start_time) * 1000,
            status="error",
            error=str(e),
        )


@router.websocket("/sam3/inference")
async def sam3_inference_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time SAM3 mask inference.

    Accepts point-based segmentation requests and returns masks with <50ms latency.
    Implements request queuing for handling multiple rapid clicks.

    Protocol:
    - Client sends: SAMPointRequest JSON
    - Server responds: SAMMaskResponse JSON
    - Server may send: SAMQueueStatusResponse for queue updates

    Args:
        websocket: WebSocket connection

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    global _is_processing

    await websocket.accept()
    logger.info("SAM3 WebSocket connection established")

    # Get database session (using dependency injection pattern)
    async for db in get_db():
        try:
            while True:
                # Receive request from client
                data = await websocket.receive_json()

                try:
                    # Validate request
                    request = SAMPointRequest(**data)

                    # Add to queue
                    await _sam_request_queue.put(
                        {"request": request, "websocket": websocket, "db": db}
                    )

                    # Send queue status
                    queue_size = _sam_request_queue.qsize()
                    await websocket.send_json(
                        SAMQueueStatusResponse(
                            queue_size=queue_size,
                            processing=_is_processing,
                            estimated_wait_ms=queue_size * 50.0,  # Estimate 50ms per request
                        ).model_dump(mode="json")
                    )

                    # Process queue if not already processing
                    async with _processing_lock:
                        if not _is_processing:
                            _is_processing = True
                            task = asyncio.create_task(_process_queue())
                            _background_tasks.add(task)
                            task.add_done_callback(_background_tasks.discard)

                except Exception as e:
                    logger.error(f"Error validating SAM request: {e}", exc_info=True)
                    await websocket.send_json(
                        {
                            "status": "error",
                            "error": f"Invalid request: {e}",
                        }
                    )

        except WebSocketDisconnect:
            logger.info("SAM3 WebSocket connection closed")
            break
        except Exception as e:
            logger.error(f"Error in SAM3 WebSocket: {e}", exc_info=True)
            break


async def _process_queue() -> None:
    """Process queued SAM inference requests sequentially.

    This runs as a background task and processes requests one at a time
    to ensure GPU memory stability and predictable latency.
    Maintains request order and provides status updates for each processed item.
    """
    global _is_processing

    try:
        while not _sam_request_queue.empty():
            # Get next request
            queue_item = await _sam_request_queue.get()
            request = queue_item["request"]
            websocket = queue_item["websocket"]
            db = queue_item["db"]

            try:
                # Log queue processing
                logger.debug(
                    f"Processing SAM request from queue: frame={request.frame_number}, "
                    f"label={request.label_id}, request_id={request.request_id}"
                )

                # Process request
                response = await _process_sam_request(request, db)

                # Send response with request_id to maintain ordering on client
                # Use mode='json' to properly serialize UUID fields
                await websocket.send_json(response.model_dump(mode="json"))

                # Log successful processing
                logger.debug(
                    f"Sent SAM response: status={response.status}, "
                    f"inference_time={response.inference_time_ms:.2f}ms"
                )

            except Exception as e:
                logger.error(f"Error processing queued SAM request: {e}", exc_info=True)
                with contextlib.suppress(Exception):
                    # Websocket may be closed, ignore send errors
                    # Convert all UUID fields to strings for JSON serialization
                    await websocket.send_json(
                        {
                            "status": "error",
                            "error": f"Processing error: {e}",
                            "request_id": request.request_id,
                            "project_id": str(request.project_id),
                            "frame_number": request.frame_number,
                            "label_id": str(request.label_id),
                        }
                    )

            finally:
                _sam_request_queue.task_done()

    finally:
        async with _processing_lock:
            _is_processing = False
            logger.debug("SAM queue processing completed")
