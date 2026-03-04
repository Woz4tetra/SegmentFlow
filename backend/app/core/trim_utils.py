"""Utilities for mapping trim ranges to frame numbers."""

from math import floor
from pathlib import Path

from app.core.video_frames import get_video_info
from app.models.project import Project


def get_trim_frame_bounds(project: Project) -> tuple[int, int] | None:
    """Return inclusive (start_frame, end_frame) bounds for a project's trim range."""
    if project.trim_start is None or project.trim_end is None:
        return None
    if not project.video_path:
        return None

    info = get_video_info(Path(project.video_path))
    if info.fps <= 0 or info.frame_count <= 0:
        return None

    start_frame = max(0, floor(project.trim_start * info.fps))
    end_frame = max(0, floor(project.trim_end * info.fps) - 1)
    end_frame = min(end_frame, info.frame_count - 1)
    if end_frame < start_frame:
        return None
    return start_frame, end_frame


def is_frame_in_trim(project: Project, frame_number: int) -> bool:
    bounds = get_trim_frame_bounds(project)
    if bounds is None:
        return True
    start_frame, end_frame = bounds
    return start_frame <= frame_number <= end_frame
