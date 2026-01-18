"""Pydantic request/response schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class ProjectBase(BaseModel):
    """Base schema for Project with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    active: bool = Field(default=True, description="Whether project is active")


class ProjectCreate(ProjectBase):
    """Schema for creating a new project.

    Attributes:
        name: Project display name
        active: Whether project is active (optional, defaults to True)
    """

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project.

    Attributes:
        name: Project display name (optional)
        stage: Current project stage (optional)
        trim_start: Start frame for trimmed video (optional)
        trim_end: End frame for trimmed video (optional)
        video_path: Path to uploaded video file (optional)
        locked_by: Client session ID that has locked this project (optional)
        active: Whether project is active (optional)
    """

    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    stage: str | None = Field(None, description="Current project stage")
    trim_start: float | None = Field(None, description="Start time for trimmed video in seconds")
    trim_end: float | None = Field(None, description="End time for trimmed video in seconds")
    video_path: str | None = Field(None, description="Path to uploaded video file")
    locked_by: str | None = Field(
        None,
        description="Client session ID that has locked this project",
    )
    active: bool | None = Field(None, description="Whether project is active")

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str | None) -> str | None:
        """Validate stage value is one of allowed values.

        Args:
            v: Stage value to validate

        Returns:
            str | None: The validated stage value

        Raises:
            ValueError: If stage is not a valid stage value
        """
        if v is not None:
            valid_stages = {
                "upload",
                "trim",
                "manual_labeling",
                "propagation",
                "validation",
                "export",
            }
            if v not in valid_stages:
                msg = f"Invalid stage: {v}. Must be one of {valid_stages}"
                raise ValueError(msg)
        return v


class ProjectResponse(ProjectBase):
    """Schema for project response.

    Attributes:
        id: Unique project identifier
        video_path: Path to uploaded video file
        trim_start: Start frame for trimmed video
        trim_end: End frame for trimmed video
        stage: Current project stage
        locked_by: Client session ID that has locked this project
        created_at: Timestamp when project was created
        updated_at: Timestamp when project was last updated
    """

    id: UUID
    video_path: str | None = None
    trim_start: float | None = None
    trim_end: float | None = None
    stage: str
    locked_by: str | None = None
    created_at: datetime
    updated_at: datetime

    # Stage visited tracking
    upload_visited: bool = False
    trim_visited: bool = False
    manual_labeling_visited: bool = False
    propagation_visited: bool = False
    validation_visited: bool = False
    export_visited: bool = False

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Schema for listing projects.

    Attributes:
        projects: List of project responses
        total: Total number of projects
    """

    projects: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")


# ===== Label Schemas =====


class LabelBase(BaseModel):
    """Base schema for Label with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Label name")
    color_hex: str = Field(..., description="Color in #RRGGBB format")
    thumbnail_path: str | None = Field(default=None, description="Optional path to label thumbnail")

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, v: str) -> str:
        """Validate color hex is in #RRGGBB format."""
        if not isinstance(v, str):
            raise ValueError("color_hex must be a string")
        if len(v) != 7 or not v.startswith("#"):
            raise ValueError("color_hex must be in format #RRGGBB")
        hex_part = v[1:]
        try:
            int(hex_part, 16)
        except ValueError as e:
            raise ValueError("color_hex must contain valid hex digits") from e
        return v


class LabelCreate(LabelBase):
    """Schema for creating a new label."""

    pass


class LabelUpdate(BaseModel):
    """Schema for updating an existing label (partial)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    color_hex: str | None = Field(None, description="Color in #RRGGBB format")
    thumbnail_path: str | None = Field(None, description="Path to thumbnail image")

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex_optional(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 7 or not v.startswith("#"):
            raise ValueError("color_hex must be in format #RRGGBB")
        try:
            int(v[1:], 16)
        except ValueError as e:
            raise ValueError("color_hex must contain valid hex digits") from e
        return v


class LabelResponse(LabelBase):
    """Schema for label response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectLabelSettingUpdate(BaseModel):
    """Schema for updating project label enable/disable."""

    enabled: bool = Field(..., description="Whether label is enabled for the project")


class ProjectLabelSettingResponse(BaseModel):
    """Schema for project label settings response."""

    id: UUID = Field(..., description="Label UUID")
    name: str = Field(..., description="Label name")
    color_hex: str = Field(..., description="Color in #RRGGBB format")
    thumbnail_path: str | None = Field(default=None, description="Optional thumbnail URL")
    enabled: bool = Field(..., description="Whether label is enabled for the project")


# ===== Video Upload Schemas =====


class VideoUploadChunkRequest(BaseModel):
    """Schema for uploading a video chunk.

    Attributes:
        chunk_number: Sequential chunk number (0-indexed)
        total_chunks: Total number of chunks in this upload
        chunk_size: Size of this chunk in bytes
        file_hash: SHA-256 hash of complete file for integrity verification
    """

    chunk_number: int = Field(..., ge=0, description="Sequential chunk number (0-indexed)")
    total_chunks: int = Field(..., gt=0, description="Total number of chunks")
    chunk_size: int = Field(..., gt=0, description="Size of this chunk in bytes")
    file_hash: str = Field(
        ..., min_length=64, max_length=64, description="SHA-256 hash of complete file"
    )


class VideoUploadProgressResponse(BaseModel):
    """Schema for video upload progress.

    Attributes:
        project_id: ID of the project
        total_size: Total size of the video file in bytes
        uploaded_size: Number of bytes uploaded so far
        progress_percent: Upload progress as percentage (0-100)
        chunks_received: Number of chunks received so far
        total_chunks: Total number of chunks expected
        status: Current upload status (uploading, completed, failed)
    """

    project_id: UUID
    total_size: int = Field(..., ge=0, description="Total size in bytes")
    uploaded_size: int = Field(..., ge=0, description="Bytes uploaded so far")
    progress_percent: float = Field(..., ge=0, le=100, description="Progress percentage")
    chunks_received: int = Field(..., ge=0, description="Number of chunks received")
    total_chunks: int = Field(..., gt=0, description="Total number of chunks")
    status: str = Field(..., description="Upload status: uploading, completed, or failed")


class VideoUploadCompleteResponse(BaseModel):
    """Schema for completed video upload response.

    Attributes:
        project_id: ID of the project
        video_path: Path where the video was saved
        file_size: Size of uploaded file in bytes
        message: Confirmation message
    """

    project_id: UUID
    video_path: str = Field(..., description="Path where video was saved")
    file_size: int = Field(..., ge=0, description="Size of uploaded file")
    message: str = Field(..., description="Confirmation message")


# ===== Image Schemas =====


class ImageResponse(BaseModel):
    """Schema for image/frame response.

    Attributes:
        id: Image UUID
        frame_number: Frame number in video sequence
        inference_path: Relative path to inference resolution image
        output_path: Relative path to output resolution image
        status: Processing status (pending, processed, failed)
        manually_labeled: Whether image has manual labels
        validation: Validation status (not_validated, passed, failed)
    """

    id: UUID
    frame_number: int = Field(..., ge=0, description="Frame number in video")
    inference_path: str | None = Field(None, description="Path to inference image")
    output_path: str | None = Field(None, description="Path to output image")
    status: str = Field(..., description="Processing status")
    manually_labeled: bool = Field(False, description="Whether manually labeled")
    validation: str = Field(..., description="Validation status")

    model_config = {"from_attributes": True}


class ImageListResponse(BaseModel):
    """Schema for listing images.

    Attributes:
        images: List of image responses
        total: Total number of images
    """

    images: list[ImageResponse] = Field(..., description="List of images")
    total: int = Field(..., ge=0, description="Total number of images")


class ImageValidationUpdate(BaseModel):
    """Schema for updating image validation status.

    Attributes:
        validation: Validation status (not_validated, passed, failed)
    """

    validation: str = Field(..., description="Validation status")

    @field_validator("validation")
    @classmethod
    def validate_validation(cls, v: str) -> str:
        valid_statuses = {"not_validated", "passed", "failed"}
        if v not in valid_statuses:
            msg = f"Invalid validation status: {v}. Must be one of {valid_statuses}"
            raise ValueError(msg)
        return v


class FrameStatus(BaseModel):
    """Schema for per-frame status used in aggregates."""

    frame_number: int = Field(..., ge=0, description="Frame number")
    status: str = Field(..., description="Processing status")
    manually_labeled: bool = Field(False, description="Whether manually labeled")
    validation: str = Field(..., description="Validation status")
    has_mask: bool = Field(False, description="Whether any mask exists")


class FrameStatusSummary(BaseModel):
    """Schema for aggregated frame status counts."""

    total_frames: int = Field(..., ge=0, description="Total number of frames")
    manual_frames: int = Field(..., ge=0, description="Frames with manual labels")
    propagated_frames: int = Field(..., ge=0, description="Frames with propagated masks")
    validated_frames: int = Field(..., ge=0, description="Frames marked passed")
    failed_frames: int = Field(..., ge=0, description="Frames marked failed")
    unlabeled_frames: int = Field(..., ge=0, description="Frames without labels")
    labels_count: int = Field(..., ge=0, description="Total labels count")


class FrameStatusAggregateResponse(BaseModel):
    """Schema for frame status aggregates."""

    frames: list[FrameStatus] = Field(..., description="Per-frame statuses")
    summary: FrameStatusSummary


# ===== SAM3 WebSocket Schemas =====


class SAMPointRequest(BaseModel):
    """Schema for SAM3 point-based mask inference request via WebSocket.

    Attributes:
        project_id: UUID of the project
        frame_number: Frame number to perform inference on
        label_id: UUID of the label/object class
        points: List of points with normalized coordinates [x, y] in range [0, 1]
        labels: List of point labels (1 for include/positive, 0 for exclude/negative)
        request_id: Optional client-generated ID to correlate request/response
    """

    project_id: UUID = Field(..., description="Project UUID")
    frame_number: int = Field(..., ge=0, description="Frame number")
    label_id: UUID = Field(..., description="Label/object UUID")
    points: list[list[float]] = Field(
        ...,
        description="Points with normalized coords [[x, y], ...]",
        min_length=1,
    )
    labels: list[int] = Field(
        ...,
        description="Point labels: 1=include, 0=exclude",
        min_length=1,
    )
    request_id: str | None = Field(None, description="Optional client request ID")

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: list[list[float]]) -> list[list[float]]:
        """Validate points are 2D with normalized coordinates.

        Args:
            v: Points to validate

        Returns:
            list[list[float]]: Validated points

        Raises:
            ValueError: If points are invalid
        """
        for point in v:
            if len(point) != 2:
                msg = f"Each point must have exactly 2 coordinates, got {len(point)}"
                raise ValueError(msg)
            x, y = point
            if not (0 <= x <= 1 and 0 <= y <= 1):
                msg = f"Point coordinates must be normalized [0, 1], got ({x}, {y})"
                raise ValueError(msg)
        return v

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: list[int], info: ValidationInfo) -> list[int]:
        """Validate labels match points length and are 0 or 1.

        Args:
            v: Labels to validate
            info: Field validation info

        Returns:
            list[int]: Validated labels

        Raises:
            ValueError: If labels are invalid
        """
        # Check if points field exists in the data
        if hasattr(info, "data") and "points" in info.data:
            points = info.data["points"]
            if len(v) != len(points):
                msg = f"Labels length ({len(v)}) must match points length ({len(points)})"
                raise ValueError(msg)

        # Validate each label is 0 or 1
        for label in v:
            if label not in {0, 1}:
                msg = f"Each label must be 0 or 1, got {label}"
                raise ValueError(msg)
        return v


class SAMMaskResponse(BaseModel):
    """Schema for SAM3 mask inference response via WebSocket.

    Attributes:
        project_id: UUID of the project
        frame_number: Frame number inference was performed on
        label_id: UUID of the label/object class
        mask_rle: Run-length encoded mask for efficient transmission (optional)
        mask_bbox: Bounding box [x, y, width, height] in pixel coordinates (optional)
        request_id: Client request ID if provided (optional)
        inference_time_ms: Time taken for inference in milliseconds
        status: Response status (success, error)
        error: Error message if status is error (optional)
    """

    project_id: UUID = Field(..., description="Project UUID")
    frame_number: int = Field(..., ge=0, description="Frame number")
    label_id: UUID = Field(..., description="Label/object UUID")
    mask_rle: str | None = Field(
        None,
        description="Run-length encoded mask (present when status is success)",
    )
    mask_bbox: list[int] | None = Field(
        None,
        description="Bounding box [x, y, width, height] in pixels (present when status is success)",
    )
    request_id: str | None = Field(None, description="Client request ID if provided")
    inference_time_ms: float = Field(..., ge=0, description="Inference time in milliseconds")
    status: str = Field(..., description="Response status: success or error")
    error: str | None = Field(
        None,
        description="Error message if status is error",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is either 'success' or 'error'.

        Args:
            v: Status value to validate

        Returns:
            str: The validated status value

        Raises:
            ValueError: If status is not 'success' or 'error'
        """
        if v not in {"success", "error"}:
            msg = f"Status must be 'success' or 'error', got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("mask_bbox")
    @classmethod
    def validate_mask_bbox(cls, v: list[int] | None) -> list[int] | None:
        """Validate mask_bbox has exactly 4 elements if provided.

        Args:
            v: Bounding box to validate

        Returns:
            list[int] | None: The validated bounding box

        Raises:
            ValueError: If bbox doesn't have exactly 4 elements
        """
        if v is not None and len(v) != 4:
            msg = f"mask_bbox must have exactly 4 elements [x, y, width, height], got {len(v)}"
            raise ValueError(msg)
        return v


# ===== Labeled Points and Masks Schemas =====


class LabeledPointCreate(BaseModel):
    """Schema for creating a labeled point.

    Attributes:
        x: Normalized x coordinate [0, 1]
        y: Normalized y coordinate [0, 1]
        include: Whether this is an include (positive) or exclude (negative) point
    """

    x: float = Field(..., ge=0, le=1, description="Normalized x coordinate")
    y: float = Field(..., ge=0, le=1, description="Normalized y coordinate")
    include: bool = Field(True, description="Include (positive) or exclude (negative) point")


class LabeledPointResponse(BaseModel):
    """Schema for labeled point response.

    Attributes:
        id: Point UUID
        label_id: Label UUID this point belongs to
        x: Normalized x coordinate
        y: Normalized y coordinate
        include: Whether this is an include or exclude point
    """

    id: UUID
    label_id: UUID
    x: float
    y: float
    include: bool

    model_config = {"from_attributes": True}


class MaskCreate(BaseModel):
    """Schema for creating a mask.

    Attributes:
        contour_polygon: Contour polygon as list of [x, y] coordinates
        area: Area of the mask in pixels
    """

    contour_polygon: list[list[float]] = Field(..., description="Contour polygon [[x, y], ...]")
    area: float = Field(..., ge=0, description="Mask area in pixels")


class MaskResponse(BaseModel):
    """Schema for mask response.

    Attributes:
        id: Mask UUID
        label_id: Label UUID this mask belongs to
        contour_polygon: Contour polygon as list of [x, y] coordinates
        area: Area of the mask in pixels
    """

    id: UUID
    label_id: UUID
    contour_polygon: list[list[float]]
    area: float

    model_config = {"from_attributes": True}


class SaveLabeledPointsRequest(BaseModel):
    """Schema for saving labeled points for an image.

    Attributes:
        label_id: UUID of the label
        points: List of points to save
    """

    label_id: UUID = Field(..., description="Label UUID")
    points: list[LabeledPointCreate] = Field(..., description="List of points to save")


class SaveMaskRequest(BaseModel):
    """Schema for saving a mask for an image.

    Attributes:
        label_id: UUID of the label
        mask: Mask data to save
    """

    label_id: UUID = Field(..., description="Label UUID")
    mask: MaskCreate = Field(..., description="Mask data to save")


class SAMQueueStatusResponse(BaseModel):
    """Schema for SAM3 queue status updates via WebSocket.

    Attributes:
        queue_size: Number of requests currently in queue
        processing: Whether a request is currently being processed
        estimated_wait_ms: Estimated wait time in milliseconds
    """

    queue_size: int = Field(..., ge=0, description="Requests in queue")
    processing: bool = Field(..., description="Whether processing active")
    estimated_wait_ms: float = Field(..., ge=0, description="Estimated wait time")


# ===== Propagation Schemas (PROP-001) =====


class PropagationPointData(BaseModel):
    """Data class for a labeled point used in propagation.

    Attributes:
        x: Normalized x coordinate [0, 1]
        y: Normalized y coordinate [0, 1]
        include: Whether this is an include (positive) or exclude (negative) point
    """

    x: float = Field(..., ge=0, le=1, description="Normalized x coordinate")
    y: float = Field(..., ge=0, le=1, description="Normalized y coordinate")
    include: bool = Field(True, description="Include (positive) or exclude (negative) point")


class PropagationLabelData(BaseModel):
    """Data class for a label's points in a propagation source frame.

    Attributes:
        label_id: UUID of the label
        label_name: Name of the label for display purposes
        color_hex: Color in #RRGGBB format
        points: List of labeled points for this label
    """

    label_id: UUID = Field(..., description="Label UUID")
    label_name: str = Field(..., description="Label name")
    color_hex: str = Field(..., description="Color in #RRGGBB format")
    points: list[PropagationPointData] = Field(..., description="Points for this label")


class PropagationSourceFrame(BaseModel):
    """Data class for a manually labeled frame used as propagation source.

    Attributes:
        frame_number: Frame number in the video
        image_id: UUID of the image
        labels: List of labels with their points for this frame
    """

    frame_number: int = Field(..., ge=0, description="Frame number")
    image_id: UUID = Field(..., description="Image UUID")
    labels: list[PropagationLabelData] = Field(..., description="Labels with points")


class PropagationSegment(BaseModel):
    """Data class for a propagation segment between two source frames.

    Attributes:
        start_frame: Starting frame number (inclusive)
        end_frame: Ending frame number (inclusive)
        source_frame: The manually labeled frame to propagate from
        direction: 'forward' or 'backward' propagation direction
        num_frames: Total number of frames in this segment
    """

    start_frame: int = Field(..., ge=0, description="Start frame (inclusive)")
    end_frame: int = Field(..., ge=0, description="End frame (inclusive)")
    source_frame: int = Field(..., ge=0, description="Source frame to propagate from")
    direction: str = Field(..., description="'forward' or 'backward'")
    num_frames: int = Field(..., ge=1, description="Number of frames in segment")


class PropagationRequest(BaseModel):
    """Schema for starting a propagation job.

    Attributes:
        project_id: UUID of the project to propagate labels for
        max_propagation_length: Optional override for max frames per segment
    """

    project_id: UUID = Field(..., description="Project UUID")
    max_propagation_length: int | None = Field(
        None,
        gt=0,
        description="Max frames per segment (uses config default if not specified)",
    )


class PropagationJobResponse(BaseModel):
    """Schema for propagation job creation response.

    Attributes:
        job_id: Unique identifier for the propagation job
        project_id: UUID of the project
        status: Job status (queued, running, completed, failed)
        total_segments: Total number of segments to propagate
        total_frames: Total number of frames to process
        message: Status message
    """

    job_id: str = Field(..., description="Unique job identifier")
    project_id: UUID = Field(..., description="Project UUID")
    status: str = Field(..., description="Job status")
    total_segments: int = Field(..., ge=0, description="Total segments to propagate")
    total_frames: int = Field(..., ge=0, description="Total frames to process")
    message: str = Field(..., description="Status message")


class PropagationProgressUpdate(BaseModel):
    """Schema for propagation progress WebSocket updates.

    Attributes:
        job_id: Unique identifier for the propagation job
        project_id: UUID of the project
        status: Current job status (running, completed, failed)
        current_segment: Current segment being processed (1-indexed)
        total_segments: Total number of segments
        current_frame: Current frame being processed
        frames_completed: Total frames completed so far
        total_frames: Total frames to process
        progress_percent: Overall progress as percentage (0-100)
        estimated_remaining_ms: Estimated time remaining in milliseconds
        error: Error message if status is 'failed'
    """

    job_id: str = Field(..., description="Unique job identifier")
    project_id: UUID = Field(..., description="Project UUID")
    status: str = Field(..., description="Job status: running, completed, failed")
    current_segment: int = Field(..., ge=0, description="Current segment (1-indexed)")
    total_segments: int = Field(..., ge=0, description="Total segments")
    current_frame: int = Field(..., ge=0, description="Current frame being processed")
    frames_completed: int = Field(..., ge=0, description="Frames completed")
    total_frames: int = Field(..., ge=0, description="Total frames to process")
    progress_percent: float = Field(..., ge=0, le=100, description="Progress percentage")
    estimated_remaining_ms: float = Field(..., ge=0, description="Estimated time remaining")
    error: str | None = Field(None, description="Error message if failed")


class PropagationStatusResponse(BaseModel):
    """Schema for querying propagation job status.

    Attributes:
        job_id: Unique identifier for the propagation job
        project_id: UUID of the project
        status: Current job status
        progress: Current progress update
        started_at: Job start timestamp
        completed_at: Job completion timestamp (if completed)
    """

    job_id: str = Field(..., description="Unique job identifier")
    project_id: UUID = Field(..., description="Project UUID")
    status: str = Field(..., description="Job status")
    progress: PropagationProgressUpdate | None = Field(None, description="Current progress")
    started_at: datetime | None = Field(None, description="Job start time")
    completed_at: datetime | None = Field(None, description="Job completion time")
