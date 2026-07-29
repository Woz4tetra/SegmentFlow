"""Tests for which propagated frames get persisted."""

import numpy as np

from app.api.v1.endpoints.propagation.shared_objects import select_frames_to_save
from app.api.v1.schemas import PropagationSegment


def make_segment(
    start_frame: int = 86,
    end_frame: int = 92,
    source_frame: int = 84,
    anchor_frame: int | None = None,
) -> PropagationSegment:
    """Build a forward segment for the selection tests."""
    return PropagationSegment(
        start_frame=start_frame,
        end_frame=end_frame,
        source_frame=source_frame,
        anchor_frame=anchor_frame,
        direction="forward",
        num_frames=(end_frame - start_frame) // 2 + 1,
    )


def make_masks(*frame_numbers: int) -> dict[int, dict[int, np.ndarray]]:
    """Build a propagation result covering the given frames."""
    return {frame: {1: np.ones((2, 2), dtype=bool)} for frame in frame_numbers}


def test_source_frame_is_saved() -> None:
    """The manually labeled source frame keeps the mask propagation derived for it.

    Skipping it leaves the weaker single-frame mask from labeling time in place, so the
    labeled frame disagrees with every propagated frame around it.
    """
    selected = select_frames_to_save(make_masks(84, 86, 88, 90, 92), make_segment())

    assert 84 in selected
    assert sorted(selected) == [84, 86, 88, 90, 92]


def test_anchor_frame_is_dropped() -> None:
    """The anchor belongs to the next segment, which writes it from its own clicks."""
    segment = make_segment(end_frame=92, anchor_frame=94)
    selected = select_frames_to_save(make_masks(84, 86, 88, 90, 92, 94), segment)

    assert 94 not in selected
    assert sorted(selected) == [84, 86, 88, 90, 92]


def test_frames_outside_the_segment_range_are_dropped() -> None:
    """Propagation can overshoot the segment; only its own range is persisted."""
    segment = make_segment(start_frame=86, end_frame=88)
    selected = select_frames_to_save(make_masks(84, 86, 88, 90, 92), segment)

    assert sorted(selected) == [84, 86, 88]


def test_source_frame_survives_a_range_that_excludes_it() -> None:
    """The source frame is kept even though it sits outside [start_frame, end_frame]."""
    segment = make_segment(start_frame=86, end_frame=88, source_frame=84)
    selected = select_frames_to_save(make_masks(84), segment)

    assert sorted(selected) == [84]
