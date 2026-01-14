"""Video frame utilities for preview and conversion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VideoInfo:
    path: Path
    fps: float
    frame_count: int
    width: int
    height: int


def _open_capture(video_path: Path) -> tuple[cv2.VideoCapture, VideoInfo]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    return cap, VideoInfo(
        path=video_path, fps=fps, frame_count=frame_count, width=width, height=height
    )


def get_video_info(video_path: Path) -> VideoInfo:
    """Return basic video info without keeping the capture open."""
    cap, info = _open_capture(video_path)
    cap.release()
    return info


def _save_single_frame(frame: np.ndarray, out_path: Path, output_width: int) -> None:
    """Save a single frame to JPEG."""
    original_height, original_width = frame.shape[0:2]
    resized_height = int(output_width * original_height / original_width)
    resized_frame = cv2.resize(
        frame, (output_width, resized_height), interpolation=cv2.INTER_LINEAR
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), resized_frame)


def convert_video_to_jpegs(
    video_path: Path,
    output_dir: Path,
    inference_dir: Path,
    output_width: int,
    inference_width: int,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Convert frames in [start_sec, end_sec] to JPEG files.

    Args:
        video_path: Path to input video
        output_dir: Output directory for download JPEGs
        inference_dir: Output directory for inference JPEGs
        output_width: Output image width
        inference_width: Inference image width
        progress_callback: Optional callable(saved, total) for progress tracking

    Returns:
        bool: Did the conversion succeed
    """
    logger.info(f"Opening {video_path}")
    cap, info = _open_capture(video_path)
    frame_indices = range(info.frame_count)

    saved = 0
    total = len(frame_indices) * 2
    did_error_occur = False
    logger.info(f"Converting to {total} images")

    try:
        for idx in frame_indices:
            logger.debug(f"Read frame {idx}")
            success, frame = cap.read()
            if not success:
                logger.error(f"Failed to extract frame index {idx}.")
                break
            for width, base_dir in ((output_width, output_dir), (inference_width, inference_dir)):
                image_out_path = base_dir / f"frame_{idx:06d}.jpg"
                logger.debug(f"Saving to {image_out_path} with width {width}")
                _save_single_frame(frame, image_out_path, width)
                saved += 1
                if progress_callback:
                    progress_callback(saved, total)
    except Exception as e:
        did_error_occur = True
        logger.error(f"Error during conversion: {e}")
    finally:
        cap.release()

    if progress_callback:
        progress_callback(saved, total)

    return did_error_occur


def generate_thumbnail(
    source_path: Path,
    output_path: Path,
    max_width: int = 320,
    quality: int = 75,
) -> Path:
    """Generate and save a compressed thumbnail from an image file.

    Args:
        source_path: Path to source image (JPEG)
        output_path: Path to save thumbnail
        max_width: Maximum width for thumbnail (maintains aspect ratio)
        quality: JPEG quality (1-100)

    Returns:
        Path to the saved thumbnail file
    """
    img = cv2.imread(str(source_path))
    if img is None:
        raise RuntimeError(f"Failed to read image: {source_path}")

    # Calculate new dimensions maintaining aspect ratio
    height, width = img.shape[:2]
    if width > max_width:
        scale = max_width / width
        new_width = max_width
        new_height = int(height * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # Encode as JPEG with specified quality
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Failed to encode thumbnail")

    # Save to disk
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(buf.tobytes())

    logger.info(f"Generated thumbnail: {output_path}")
    return output_path
