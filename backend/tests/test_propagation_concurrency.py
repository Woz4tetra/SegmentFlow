"""Concurrency safety tests for propagation and manual labeling."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import threading

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.projects.save_labeled_points import _run_sam_inference
from app.api.v1.endpoints.propagation import shared_objects
from app.api.v1.endpoints.propagation.shared_objects import process_segment
from app.api.v1.schemas import PropagationSegment
from app.models.project import Project


class _FakeTracker:
    def __init__(self) -> None:
        self.called_images_dir: str | None = None
        self.calls: list[str] = []

    def propagate_from_project(
        self,
        images_dir: str,
        source_frame: int,
        _points_by_obj,
        _propagate_length: int,
        _additional_points_by_frame,
        callback,
    ):
        self.called_images_dir = images_dir
        self.calls.append(images_dir)
        if callback:
            callback(source_frame + 1, 1.0, 0.0)
        return {source_frame + 1: {1: np.ones((2, 2), dtype=bool)}}, {}

    def get_single_frame_mask_for_project(
        self,
        images_dir: str,
        _frame_number: int,
        _obj_id: int,
        _points: np.ndarray,
        _labels: np.ndarray,
    ) -> np.ndarray:
        self.called_images_dir = images_dir
        return np.ones((2, 2), dtype=np.uint8)


@pytest.fixture(autouse=True)
def _reset_propagation_globals() -> None:
    shared_objects.propagation_jobs.clear()
    shared_objects.job_websockets.clear()
    shared_objects.tracker_queue = None
    shared_objects.tracker_count = 0


@pytest.mark.asyncio
async def test_start_propagation_reuses_active_project_job(
    client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = Project(name="Propagation Reuse", active=True, stage="propagation")
    db.add(project)
    await db.commit()
    await db.refresh(project)

    async def fake_analyze(*_args, **_kwargs):
        return (
            [
                PropagationSegment(
                    start_frame=1,
                    end_frame=2,
                    source_frame=0,
                    anchor_frame=None,
                    direction="forward",
                    num_frames=2,
                )
            ],
            [{"frame_number": 0, "image_id": uuid4(), "points_by_label": {}}],
        )

    async def fake_run_job(*_args, **_kwargs):
        await asyncio.sleep(0.1)

    monkeypatch.setattr(
        "app.api.v1.endpoints.propagation.start_propagation.analyze_propagation_segments",
        fake_analyze,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.propagation.start_propagation.run_propagation_job",
        fake_run_job,
    )

    payload = {"project_id": str(project.id)}
    first = await client.post(f"/api/v1/projects/{project.id}/propagate", json=payload)
    second = await client.post(f"/api/v1/projects/{project.id}/propagate", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert "active propagation job" in second.json()["message"].lower()


@pytest.mark.asyncio
async def test_shared_tracker_queue_reserves_primary_tracker(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = SimpleNamespace(gpu_id=0)
    trackers = {0: SimpleNamespace(gpu_id=0), 1: SimpleNamespace(gpu_id=1)}

    monkeypatch.setattr(shared_objects, "get_primary_tracker", lambda: primary)
    monkeypatch.setattr(shared_objects, "get_all_trackers", lambda: trackers)

    queue = await shared_objects._ensure_tracker_queue()
    entries = []
    while not queue.empty():
        entries.append(await queue.get())

    assert shared_objects.tracker_count == 1
    assert entries[0][0] == 1


@pytest.mark.asyncio
async def test_process_segment_uses_project_scoped_propagation(monkeypatch: pytest.MonkeyPatch) -> None:
    tracker = _FakeTracker()
    inference_dir = "/tmp/project-a/inference"

    async def fake_acquire():
        return 7, tracker

    async def fake_release(_entry):
        return None

    async def fake_save_segment_masks(*_args, **_kwargs):
        return None

    class _FakeDb:
        async def close(self) -> None:
            return None

    async def db_factory() -> AsyncGenerator[_FakeDb, None]:
        yield _FakeDb()

    monkeypatch.setattr(shared_objects, "_acquire_tracker", fake_acquire)
    monkeypatch.setattr(shared_objects, "_release_tracker", fake_release)
    monkeypatch.setattr(shared_objects, "save_segment_masks", fake_save_segment_masks)

    segment = PropagationSegment(
        start_frame=1,
        end_frame=1,
        source_frame=0,
        anchor_frame=None,
        direction="forward",
        num_frames=1,
    )
    source_data_by_frame = {0: {"points_by_label": {uuid4(): [{"x": 0.5, "y": 0.5, "include": True}]}}}
    progress_state = {"completed_frames": 0, "segment_progress": {}}

    await process_segment(
        segment=segment,
        seg_idx=0,
        segments=[segment],
        source_data_by_frame=source_data_by_frame,
        job_id="job-1",
        project_id=uuid4(),
        job={"status": "running"},
        total_frames=1,
        progress_state=progress_state,
        progress_lock=threading.Lock(),
        start_time=0.0,
        inference_dir=inference_dir,
        db_factory=db_factory,
    )

    assert tracker.called_images_dir == inference_dir


@pytest.mark.asyncio
async def test_manual_inference_uses_project_scoped_tracker_method() -> None:
    tracker = _FakeTracker()
    inference_dir = Path("/tmp/project-b/inference")

    mask = await _run_sam_inference(
        tracker=tracker,
        inference_dir=inference_dir,
        frame_number=3,
        label_id=uuid4(),
        points=[(0.25, 0.25)],
        labels=[1],
    )

    assert mask is not None
    assert tracker.called_images_dir == str(inference_dir)
