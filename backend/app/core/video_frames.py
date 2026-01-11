"""Video frame utilities for preview and conversion."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

import cv2

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
    return cap, VideoInfo(path=video_path, fps=fps, frame_count=frame_count, width=width, height=height)


def get_video_info(video_path: Path) -> VideoInfo:
    """Return basic video info without keeping the capture open."""
    cap, info = _open_capture(video_path)
    cap.release()
    return info


def read_frame_at_time(video_path: Path, time_sec: float) -> bytes:
    """Read a single frame at the given time and return JPEG bytes."""
    cap, info = _open_capture(video_path)
    try:
        frame_index = int(max(0.0, time_sec) * info.fps)
        frame_index = min(frame_index, max(info.frame_count - 1, 0))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"Failed to read frame at index {frame_index}")
        # Convert BGR -> RGB for consistency then encode JPEG
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ok, buf = cv2.imencode('.jpg', frame_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise RuntimeError("Failed to encode frame as JPEG")
        return buf.tobytes()
    finally:
        cap.release()


def _save_single_frame(args: tuple[str, int, str]) -> bool:
    """Worker to save a single frame at a given index to JPEG."""
    video_path_str, frame_index, out_path_str = args
    video_path = Path(video_path_str)
    out_path = Path(out_path_str)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        return False
    ok2, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok2:
        cap.release()
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(buf.tobytes())
    cap.release()
    return True


def convert_range_to_jpegs(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    output_dir: Path,
    processes: int | None = None,
) -> dict:
    """Convert frames in [start_sec, end_sec] to JPEG files.

    Returns summary with total and saved counts.
    """
    cap, info = _open_capture(video_path)
    try:
        fps = max(info.fps, 1.0)
        start_frame = int(max(0.0, start_sec) * fps)
        end_frame = int(max(start_sec, end_sec) * fps)
        end_frame = min(end_frame, max(info.frame_count - 1, 0))
        if end_frame <= start_frame:
            return {"total": 0, "saved": 0}
        frame_indices = list(range(start_frame, end_frame + 1))
    finally:
        cap.release()

    tasks: Iterable[tuple[str, int, str]] = (
        (str(video_path), idx, str(output_dir / f"frame_{idx:06d}.jpg")) for idx in frame_indices
    )

    saved = 0
    # Use multiprocessing pool if requested; otherwise run sequentially
    try:
        if processes and processes > 1:
            import multiprocessing as mp
            with mp.Pool(processes=processes) as pool:
                for ok in pool.imap_unordered(_save_single_frame, tasks, chunksize=16):
                    saved += 1 if ok else 0
        else:
            for t in tasks:
                if _save_single_frame(t):
                    saved += 1
    except Exception as e:
        logger.error(f"Error during conversion: {e}")

    return {"total": len(frame_indices), "saved": saved}
