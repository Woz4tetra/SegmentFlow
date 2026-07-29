"""Video frame utilities for preview and conversion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.crop_utils import CropRect, crop_frame
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


def read_frame_at_index(video_path: Path, frame_index: int) -> np.ndarray | None:
    """Decode a single uncropped frame directly from the source video.

    Args:
        video_path: Path to input video
        frame_index: Frame index to seek to (0-indexed, clamped to the video length)

    Returns:
        np.ndarray | None: The decoded frame, or None if it could not be read
    """
    cap, info = _open_capture(video_path)
    try:
        target = max(0, min(frame_index, max(info.frame_count - 1, 0)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        success, frame = cap.read()
        if not success:
            logger.warning(f"Failed to read frame {target} from {video_path}")
            return None
        return frame
    finally:
        cap.release()


def resize_to_width(frame: np.ndarray, target_width: int) -> np.ndarray:
    """Resize a frame to the target width, preserving aspect ratio.

    Args:
        frame: Frame as a HxWxC array
        target_width: Desired output width in pixels

    Returns:
        np.ndarray: The resized frame
    """
    original_height, original_width = frame.shape[0:2]
    if original_width <= 0 or original_height <= 0 or original_width == target_width:
        return frame
    target_height = max(1, int(target_width * original_height / original_width))
    return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)


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
    desired_fps: float | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    crop: CropRect | None = None,
) -> bool:
    """Convert frames in [start_sec, end_sec] to JPEG files.

    Args:
        video_path: Path to input video
        output_dir: Output directory for download JPEGs
        inference_dir: Output directory for inference JPEGs
        output_width: Output image width
        inference_width: Inference image width
        progress_callback: Optional callable(saved, total) for progress tracking
        crop: Optional normalized crop applied to every frame before resizing

    Returns:
        bool: Did the conversion succeed
    """
    logger.info(f"Opening {video_path}")
    cap, info = _open_capture(video_path)
    frame_indices = _build_sampled_frame_indices(info.frame_count, info.fps, desired_fps)
    frame_set = set(frame_indices)

    saved = 0
    total = len(frame_indices) * 2
    did_error_occur = False
    logger.info(f"Converting to {total} images")

    try:
        for idx in range(info.frame_count):
            logger.debug(f"Read frame {idx}")
            success, frame = cap.read()
            if not success:
                # Containers routinely report a frame count a little past the last
                # decodable frame, so stopping early is only fatal if we got nothing.
                logger.error(f"Failed to extract frame index {idx}.")
                break
            if idx not in frame_set:
                continue
            # Crop once so both resolutions cover the identical region
            frame = crop_frame(frame, crop)
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

    if saved == 0 and total > 0:
        did_error_occur = True
        logger.error(f"No frames could be decoded from {video_path}")

    if progress_callback:
        progress_callback(total, total)

    return did_error_occur


def _build_sampled_frame_indices(
    frame_count: int,
    source_fps: float,
    desired_fps: float | None,
) -> list[int]:
    """Build source frame indices for extraction at desired fps."""
    if frame_count <= 0:
        return []
    if desired_fps is None or source_fps <= 0:
        return list(range(frame_count))

    clamped_desired = max(1.0, min(float(desired_fps), float(source_fps)))
    if clamped_desired >= source_fps:
        return list(range(frame_count))

    step = source_fps / clamped_desired
    indices: list[int] = []
    seen: set[int] = set()
    pos = 0.0
    while True:
        idx = int(round(pos))
        if idx >= frame_count:
            break
        if idx not in seen:
            seen.add(idx)
            indices.append(idx)
        pos += step
    if not indices:
        indices.append(0)
    return indices


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
