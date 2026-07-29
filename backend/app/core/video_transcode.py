"""Normalize source videos that OpenCV cannot decode.

OpenCV ships its own FFmpeg build, and that build carries only the hardware-backed
AV1 stub — on this deployment it fails with "Your platform doesn't support hardware
accelerated AV1 decoding" and every ``cap.read()`` returns False. The standalone
``ffmpeg`` binary in the image has ``libdav1d`` and decodes those files fine, so any
video OpenCV chokes on is re-encoded to H.264 once, up front, and everything
downstream keeps using ``cv2.VideoCapture`` unchanged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2

from app.core.logging import get_logger

logger = get_logger(__name__)

# Suffix for the normalized copy, kept next to the original.
TRANSCODED_SUFFIX = "_h264"

# veryfast/CRF 20 keeps a 1080p60 clip well under a minute; frames are resized and
# re-encoded to JPEG downstream, so extra fidelity here would be wasted.
_FFMPEG_ARGS = [
    "-map",
    "0:v:0",
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    "-an",
]

_TRANSCODE_TIMEOUT_SEC = 3600


def is_opencv_readable(video_path: Path) -> bool:
    """Report whether OpenCV can actually decode a frame from the video.

    Opening succeeds for containers whose codec OpenCV cannot decode, so this
    decodes a frame rather than trusting ``isOpened()``.

    Args:
        video_path: Path to the video file

    Returns:
        True if the first frame decodes, False otherwise
    """
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return False
        success, frame = cap.read()
        return bool(success) and frame is not None
    finally:
        cap.release()


def transcode_to_h264(source_path: Path, target_path: Path) -> None:
    """Re-encode a video to H.264 with the standalone ffmpeg binary.

    Args:
        source_path: Video to read
        target_path: Destination file, overwritten if present

    Raises:
        RuntimeError: If ffmpeg is missing, fails, or takes too long
    """
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source_path),
        *_FFMPEG_ARGS,
        str(target_path),
    ]
    logger.info(f"Transcoding {source_path} to H.264 at {target_path}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_TRANSCODE_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg is not installed, cannot transcode video") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Transcode of {source_path} timed out") from e

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {source_path}: {result.stderr.strip()}")


def ensure_opencv_readable(video_path: Path) -> Path:
    """Return a path to this video that OpenCV can decode, transcoding if needed.

    Args:
        video_path: Path to the source video

    Returns:
        The original path when it is already readable, otherwise the path to the
        H.264 copy sitting alongside it

    Raises:
        RuntimeError: If the video needs transcoding and that fails
    """
    if is_opencv_readable(video_path):
        return video_path

    transcoded_path = video_path.with_name(f"{video_path.stem}{TRANSCODED_SUFFIX}.mp4")
    if transcoded_path.exists() and is_opencv_readable(transcoded_path):
        logger.info(f"Reusing existing transcode {transcoded_path}")
        return transcoded_path

    logger.warning(f"OpenCV cannot decode {video_path}, transcoding to H.264")
    transcode_to_h264(video_path, transcoded_path)

    if not is_opencv_readable(transcoded_path):
        raise RuntimeError(f"Transcoded video is still unreadable: {transcoded_path}")

    logger.info(f"Transcode complete, using {transcoded_path}")
    return transcoded_path
