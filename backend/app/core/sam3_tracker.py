"""SAM3 video segmentation tracker integration with memory-efficient frame loading.

This module provides SAM3Tracker, a wrapper for SAM3 video segmentation model with:
- Memory-efficient frame loading via symlinks/temporary directories
- Single-GPU support for parallel propagation across multiple GPUs
- CUDA memory management and cleanup
- Real-time mask inference and propagation
"""

import contextlib
import gc
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from natsort import natsorted
from sam3.model_builder import build_sam3_video_model  # type: ignore
from tqdm import tqdm

from app.core.logging import get_logger

logger = get_logger(__name__)

# Supported image extensions
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


class SAM3Tracker:
    """Wrapper for SAM3 video segmentation model with memory-efficient frame loading.

    Works with folders of images. For propagation, creates a temporary directory
    with symlinks to the original images (scaled if needed). This avoids copying
    images while still providing SAM3 with the sequential file naming it expects.

    Designed for parallel execution across multiple GPUs - create one instance
    per GPU for concurrent propagation of multiple labeled segments.
    """

    def __init__(self, gpu_id: int = 0, inference_width: int = 960):
        """Initialize the tracker for a specific GPU.

        Args:
            gpu_id: GPU device ID to use (default: 0)
            inference_width: Target width in pixels for inference.
                           Height is calculated to maintain aspect ratio.
        """
        self.gpu_id = gpu_id
        self.inference_width = inference_width

        # Current active model references
        self.model: Any = None
        self.predictor: Any = None
        self.device: torch.device | None = None
        self.inference_state: Any = None

        # Image folder info (loaded lazily)
        self.images_dir: Path | None = None
        self.image_files: list[Path] = []  # Sorted list of image paths
        self.image_width: int = 0
        self.image_height: int = 0
        self.total_frames: int = 0

        # Scaled dimensions for inference
        self.scaled_width: int = 0
        self.scaled_height: int = 0

        # Temporary directory for scaled frames (only used if scaling needed)
        self._temp_dir: str | None = None
        self._original_frames: dict[int, np.ndarray] = {}  # frame_idx -> original resolution frame

        # Lock for thread-safe temp directory management
        self._temp_dir_lock = threading.Lock()

        # Lock for inference operations - ensures only one inference runs at a time
        # This prevents race conditions where a new request deletes temp files
        # while a previous request's SAM3 init_state is still loading them
        self._inference_lock = threading.Lock()

        # Set up device (model loaded lazily on first use)
        self.device = torch.device(f"cuda:{self.gpu_id}" if torch.cuda.is_available() else "cpu")

        logger.info(
            f"SAM3Tracker initialized for GPU {self.gpu_id}, inference width: {inference_width}"
        )

    def _setup_device_optimizations(self) -> None:
        """Enable optimizations for the GPU (call once before using GPU)."""
        if not torch.cuda.is_available():
            return

        torch.cuda.set_device(self.gpu_id)
        device_props = torch.cuda.get_device_properties(self.gpu_id)
        if device_props.major >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            logger.debug(f"Enabled TF32 optimizations for GPU {self.gpu_id}")

    def _unload_model(self) -> None:
        """Fully unload model from GPU to free memory."""
        if self.model is None:
            return

        logger.info(f"Unloading model from cuda:{self.gpu_id}...")

        # Clear inference state first
        self._reset_inference_state()

        # Delete predictor reference (it references model internals)
        self.predictor = None

        # Move all model parameters and buffers to CPU explicitly
        try:
            self.model.cpu()
            # Also clear any cached states in the model
            if hasattr(self.model, "tracker") and self.model.tracker is not None:
                if hasattr(self.model.tracker, "_cached_features"):
                    self.model.tracker._cached_features = None
                if hasattr(self.model.tracker, "memory_bank"):
                    self.model.tracker.memory_bank = None
        except Exception as e:
            logger.warning(f"Warning during model CPU transfer: {e}")

        # Delete model
        del self.model
        self.model = None

        # Force multiple rounds of garbage collection
        for _ in range(3):
            gc.collect()

        # Clear GPU cache aggressively
        if torch.cuda.is_available() and self.gpu_id is not None:
            try:
                with torch.cuda.device(self.gpu_id):
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()  # Also collect IPC memory
                    torch.cuda.synchronize()
            except Exception as e:
                logger.warning(f"Error clearing GPU cache: {e}")

        # Additional gc after CUDA cleanup
        gc.collect()

        logger.info(f"Model unloaded from cuda:{self.gpu_id}")

    def _load_model_on_current_gpu(self) -> None:
        """Load SAM3 model on the GPU device."""
        if build_sam3_video_model is None:
            raise RuntimeError("SAM3 not installed.")

        logger.info(f"Loading SAM3 model on cuda:{self.gpu_id}...")

        # Set up device and optimizations
        self.device = torch.device(f"cuda:{self.gpu_id}")
        self._setup_device_optimizations()

        # CRITICAL: Set the default CUDA device BEFORE building the model
        # This ensures all tensors are created on the correct GPU from the start
        with torch.cuda.device(self.gpu_id), torch.autocast("cuda", dtype=torch.bfloat16):
            self.model = build_sam3_video_model()
            if self.model is not None:
                self.model = self.model.to(self.device)
                self.predictor = self.model.tracker
                self.predictor.backbone = self.model.detector.backbone

        logger.info(f"SAM3 model loaded successfully on cuda:{self.gpu_id}")

    def load_model(self) -> None:
        """Load SAM3 model on the current GPU device."""
        if self.model is not None:
            return  # Already loaded
        self._load_model_on_current_gpu()

    def set_video(self, video_path: str) -> None:
        """Set the images directory to work with.

        Args:
            video_path: Path to directory containing images
        """
        self.set_images_dir(video_path)

    def set_images_dir(self, images_dir: str) -> None:
        """Set the images directory to work with.

        Args:
            images_dir: Path to directory containing images

        Raises:
            FileNotFoundError: If directory doesn't exist
            ValueError: If path is not a directory or contains no images
        """
        if self.predictor is None:
            self.load_model()

        self.images_dir = Path(images_dir)

        if not self.images_dir.exists():
            raise FileNotFoundError(f"Images directory not found: {images_dir}")

        if not self.images_dir.is_dir():
            raise ValueError(f"Path is not a directory: {images_dir}")

        # Load and sort image files
        self.image_files = []
        for ext in SUPPORTED_EXTENSIONS:
            self.image_files.extend(self.images_dir.glob(f"*{ext}"))
            self.image_files.extend(self.images_dir.glob(f"*{ext.upper()}"))

        # Natural sort to handle numeric naming correctly
        self.image_files = natsorted(self.image_files, key=lambda p: p.name)

        if not self.image_files:
            raise ValueError(f"No images found in: {images_dir}")

        self.total_frames = len(self.image_files)

        # Load first image to get dimensions
        first_image = cv2.imread(str(self.image_files[0]))
        if first_image is None:
            raise ValueError(f"Cannot read image: {self.image_files[0]}")

        self.image_height, self.image_width = first_image.shape[:2]

        # Calculate scaled dimensions from target width
        if self.inference_width >= self.image_width:
            # No scaling needed if target is >= original
            self.scaled_width = self.image_width
            self.scaled_height = self.image_height
        else:
            # Scale to target width, maintain aspect ratio
            scale = self.inference_width / self.image_width
            self.scaled_width = self.inference_width
            self.scaled_height = int(self.image_height * scale)

        # Ensure dimensions are even (required by many video codecs)
        self.scaled_width = self.scaled_width - (self.scaled_width % 2)
        self.scaled_height = self.scaled_height - (self.scaled_height % 2)

        logger.info(f"Images: {self.image_width}x{self.image_height}, {self.total_frames} frames")
        logger.info(
            f"Inference width: {self.inference_width} -> {self.scaled_width}x{self.scaled_height}"
        )

        # Note: We do NOT clean up temp directory here because set_images_dir() can be
        # called outside the inference lock. Cleanup is handled safely in:
        # 1. _prepare_frames_for_propagation() - cleans old dir after new one is created
        # 2. End of inference methods (get_preview_mask, etc.) - cleans up after use

    def _cleanup_temp_dir(self) -> None:
        """Clean up temporary frame directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
        self._original_frames = {}

    def _reset_inference_state(self) -> None:
        """Reset the inference state to free GPU memory while keeping model loaded."""
        if self.inference_state is not None:
            # Use SAM3's reset_state if available to properly clean up
            if self.predictor is not None and hasattr(self.predictor, "reset_state"):
                with contextlib.suppress(Exception):
                    self.predictor.reset_state(self.inference_state)
                    # Ignore errors during reset

            # Clear all references in the inference state dict
            if isinstance(self.inference_state, dict):
                # Clear internal tensors that may be holding GPU memory
                for key in list(self.inference_state.keys()):
                    val = self.inference_state[key]
                    if isinstance(val, torch.Tensor):
                        del self.inference_state[key]
                    elif isinstance(val, dict):
                        val.clear()
                self.inference_state.clear()

            # Clear the reference
            self.inference_state = None

        # Force garbage collection to free GPU memory
        gc.collect()

        # Clear GPU memory cache for the current device
        if torch.cuda.is_available() and self.gpu_id is not None:
            try:
                with torch.cuda.device(self.gpu_id):
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            except Exception as e:
                logger.debug(f"Error clearing GPU cache: {e}")

    def _prepare_frames_for_propagation(
        self,
        start_frame: int,
        num_frames: int,
    ) -> str:
        """Prepare frames for SAM3 inference by creating a temp directory with sequential file naming.

        Uses symlinks if no scaling needed, otherwise creates scaled copies.

        Args:
            start_frame: Starting frame index
            num_frames: Number of frames to process

        Returns:
            Path to directory containing prepared frames

        Raises:
            ValueError: If image cannot be read
        """
        # Reset inference state first to free GPU memory
        self._reset_inference_state()

        end_frame = min(start_frame + num_frames, self.total_frames)
        actual_num_frames = end_frame - start_frame

        if actual_num_frames <= 0:
            raise ValueError(
                f"Invalid frame range: start={start_frame}, num_frames={num_frames}, total_frames={self.total_frames}"
            )

        logger.info(
            f"Preparing {actual_num_frames} frames starting at {start_frame} (frames {start_frame} to {end_frame - 1})..."
        )

        # Store old temp dir to clean up later (after new one is created)
        old_temp_dir = self._get_and_create_temp_dir()

        # Check if scaling is needed
        needs_scaling = self.scaled_width != self.image_width

        if needs_scaling:
            frames_created = self._create_scaled_frames(start_frame, end_frame)
            logger.info(f"Created {frames_created} scaled frames in {self._temp_dir}")
        else:
            frames_created = self._create_symlinked_frames(start_frame, end_frame)
            if frames_created == 0:
                raise ValueError(
                    f"No frames were created. Requested {actual_num_frames} frames starting from {start_frame}, "
                    f"but all source frames were missing or unreadable."
                )
            logger.info(
                f"Created {frames_created} frames in {self._temp_dir} (requested {actual_num_frames})"
            )

        # Clean up old temp directory after new one is successfully created
        self._cleanup_old_temp_dir(old_temp_dir)

        assert self._temp_dir is not None, "Temp directory should have been created"
        return self._temp_dir

    def _get_and_create_temp_dir(self) -> str | None:
        """Get current temp dir and create a new one.

        Returns:
            Path to old temp directory (if any)
        """
        with self._temp_dir_lock:
            old_temp_dir = self._temp_dir
            self._temp_dir = tempfile.mkdtemp(prefix="sam3_frames_")
        return old_temp_dir

    def _cleanup_old_temp_dir(self, old_temp_dir: str | None) -> None:
        """Clean up old temp directory if it exists and is different from current.

        Args:
            old_temp_dir: Path to old temp directory to clean up
        """
        with self._temp_dir_lock:
            new_temp_dir = self._temp_dir
            if old_temp_dir and old_temp_dir != new_temp_dir and os.path.exists(old_temp_dir):
                try:
                    shutil.rmtree(old_temp_dir, ignore_errors=True)
                    logger.debug(f"Cleaned up old temp directory: {old_temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up old temp directory {old_temp_dir}: {e}")

    def _load_frame(self, frame_idx: int) -> tuple[Path, np.ndarray] | None:
        """Load a frame from disk.

        Args:
            frame_idx: Frame index to load

        Returns:
            Tuple of (image_path, frame_array) or None if frame cannot be loaded
        """
        if frame_idx >= len(self.image_files):
            logger.warning(
                f"Frame index {frame_idx} out of range (total: {len(self.image_files)}), skipping"
            )
            return None

        image_path = self.image_files[frame_idx]

        if not image_path.exists():
            logger.warning(f"Image file does not exist: {image_path}, skipping")
            return None

        frame = cv2.imread(str(image_path))
        if frame is None:
            logger.warning(f"Cannot read image: {image_path}, skipping")
            return None

        return image_path, frame

    def _create_scaled_frames(self, start_frame: int, end_frame: int) -> int:
        """Create scaled copies of frames in temp directory.

        Args:
            start_frame: Starting frame index
            end_frame: Ending frame index (exclusive)

        Returns:
            Number of frames created

        Raises:
            ValueError: If frame cannot be read
        """
        assert self._temp_dir is not None, "Temp directory must be created first"
        frames_created = 0
        for local_idx, frame_idx in enumerate(
            tqdm(range(start_frame, end_frame), desc="Scaling frames")
        ):
            result = self._load_frame(frame_idx)
            if result is None:
                raise ValueError(f"Cannot load frame {frame_idx}")

            _, frame = result

            # Store original resolution frame for later use
            self._original_frames[frame_idx] = frame.copy()

            # Scale down frame
            scaled_frame = cv2.resize(
                frame,
                (self.scaled_width, self.scaled_height),
                interpolation=cv2.INTER_AREA,
            )

            # Save with sequential naming
            frame_path = os.path.join(self._temp_dir, f"{local_idx:06d}.jpg")
            cv2.imwrite(frame_path, scaled_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            frames_created += 1

        return frames_created

    def _create_symlinked_frames(self, start_frame: int, end_frame: int) -> int:
        """Create symlinks or copies of frames in temp directory.

        Args:
            start_frame: Starting frame index
            end_frame: Ending frame index (exclusive)

        Returns:
            Number of frames created
        """
        frames_created = 0
        for frame_idx in range(start_frame, end_frame):
            result = self._load_frame(frame_idx)
            if result is None:
                continue

            image_path, frame = result

            # Store original resolution frame for later use
            self._original_frames[frame_idx] = frame

            # Use the actual number of frames created so far as the local index
            # This ensures sequential naming without gaps
            local_idx = frames_created

            # Create frame link or copy
            if self._create_frame_link_or_copy(image_path, frame, local_idx):
                frames_created += 1

        return frames_created

    def _create_frame_link_or_copy(
        self, image_path: Path, frame: np.ndarray, local_idx: int
    ) -> bool:
        """Create a symlink or copy of a frame in the temp directory.

        Args:
            image_path: Path to source image
            frame: Loaded frame array
            local_idx: Local index for sequential naming

        Returns:
            True if frame was created successfully, False otherwise
        """
        assert self._temp_dir is not None, "Temp directory must be created first"
        target_path = os.path.join(self._temp_dir, f"{local_idx:06d}.jpg")

        # SAM3 only supports JPEG format - must convert if not JPEG
        if image_path.suffix.lower() in {".jpg", ".jpeg"}:
            # Try to create symlink first
            try:
                source_path = image_path.resolve()
                if not source_path.exists():
                    logger.warning(f"Source image does not exist: {source_path}, skipping")
                    return False
                os.symlink(str(source_path), target_path)
                logger.debug(f"Created symlink: {target_path} -> {source_path}")
                return True
            except (OSError, ValueError) as e:
                # If symlink fails, copy the file instead
                logger.warning(f"Symlink failed for {image_path}, copying instead: {e}")
                cv2.imwrite(target_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                return True
        else:
            # Convert to JPEG for SAM3 compatibility
            cv2.imwrite(target_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            return True

    def _init_inference_state(self, frames_dir: str) -> None:
        """Initialize SAM3 inference state with extracted frames directory.

        Args:
            frames_dir: Path to directory with frames

        Raises:
            RuntimeError: If model not loaded
        """
        # Ensure model is loaded (may have been unloaded during GPU cycling)
        if self.predictor is None:
            self.load_model()

        logger.info(f"Initializing inference state from: {frames_dir} on cuda:{self.gpu_id}")

        # Ensure we're on the correct GPU when initializing inference state
        with torch.cuda.device(self.gpu_id):
            if self.predictor is not None:
                self.inference_state = self.predictor.init_state(video_path=frames_dir)

        logger.info("Inference state initialized")

    def _scale_mask_to_original(self, mask: np.ndarray) -> np.ndarray:
        """Scale a mask from inference resolution back to original image resolution.

        Args:
            mask: Binary mask at inference resolution

        Returns:
            Binary mask at original image resolution
        """
        # No scaling needed if dimensions match
        if self.scaled_width == self.image_width:
            return mask

        # Ensure mask is 2D
        if mask.ndim == 3:
            mask = mask.squeeze()

        # Scale up using nearest neighbor to preserve binary values
        scaled = cv2.resize(
            mask.astype(np.uint8),
            (self.image_width, self.image_height),
            interpolation=cv2.INTER_NEAREST,
        )

        return scaled.astype(bool)

    def add_points(
        self,
        local_frame_idx: int,
        obj_id: int,
        points: np.ndarray,
        labels: np.ndarray,
        clear_old: bool = False,
    ) -> np.ndarray | None:
        """Add point prompts for an object on a specific frame.

        Args:
            local_frame_idx: Frame index relative to extracted frames (0-based)
            obj_id: Object ID
            points: Points array with normalized coordinates [[x, y], ...]
            labels: Labels array [1, 0, ...] (1=positive, 0=negative)
            clear_old: Whether to clear existing points for this object

        Returns:
            Predicted mask for the frame at ORIGINAL resolution, or None
        """
        if self.inference_state is None:
            raise RuntimeError("Inference state not initialized")

        if len(points) == 0:
            return None

        # Create tensors on the correct device
        with torch.cuda.device(self.gpu_id):
            points_tensor = torch.tensor(points, dtype=torch.float32, device=self.device)
            labels_tensor = torch.tensor(labels, dtype=torch.int32, device=self.device)

            _, out_obj_ids, _low_res_masks, video_res_masks = self.predictor.add_new_points(
                inference_state=self.inference_state,
                frame_idx=local_frame_idx,
                obj_id=obj_id,
                points=points_tensor,
                labels=labels_tensor,
                clear_old_points=clear_old,
            )

        # Return the mask for this object, scaled to original size
        if video_res_masks is not None:
            for i, oid in enumerate(out_obj_ids):
                if oid == obj_id:
                    mask = (video_res_masks[i] > 0.0).cpu().numpy()
                    return self._scale_mask_to_original(mask)

        return None

    def propagate_from_frame(
        self,
        source_frame: int,
        points_by_obj: dict[int, tuple[np.ndarray, np.ndarray]],
        propagate_length: int,
        additional_points_by_frame: dict[int, dict[int, tuple[np.ndarray, np.ndarray]]] | None = None,
        callback: Callable[[int, float], None] | None = None,
    ) -> tuple[dict[int, dict[int, np.ndarray]], dict[int, np.ndarray]]:
        """Prepare frames, add points, and propagate masks.

        This is the main entry point for propagation. It:
        1. Prepares frames in a temp directory (symlinks or scaled copies)
        2. Initializes SAM3 with those frames
        3. Adds the point prompts
        4. Propagates through the frames
        5. Scales masks back to original resolution

        Args:
            source_frame: Frame index to start from
            points_by_obj: Dict of {obj_id: (points, labels)} with normalized coords
            propagate_length: Number of frames to propagate
            additional_points_by_frame: Optional mapping of frame_idx to points_by_obj
            callback: Optional callback(frame_idx, progress) for progress updates

        Returns:
            Tuple of:
            - Dict of {frame_idx: {obj_id: mask_at_original_resolution}}
            - Dict of {frame_idx: frame_at_original_resolution}

        Raises:
            RuntimeError: If no images directory set
        """
        if self.images_dir is None:
            raise RuntimeError("No images directory set. Call set_images_dir() first.")

        # Use inference lock to prevent race conditions
        with self._inference_lock:
            # Clamp propagate_length to not exceed available frames
            max_frames = min(propagate_length, self.total_frames - source_frame)

            # Prepare frames in temp directory
            frames_dir = self._prepare_frames_for_propagation(source_frame, max_frames)

            # Initialize inference state with prepared frames
            self._init_inference_state(frames_dir)

            # Add points for each object (at local frame index 0)
            local_source_idx = 0  # Source frame is always at index 0 in temp directory
            for obj_id, (points, labels) in points_by_obj.items():
                if len(points) > 0:
                    self.add_points(
                        local_frame_idx=local_source_idx,
                        obj_id=obj_id,
                        points=points,
                        labels=labels,
                        clear_old=True,
                    )

            if additional_points_by_frame:
                for frame_idx, frame_points in additional_points_by_frame.items():
                    local_frame_idx = frame_idx - source_frame
                    if local_frame_idx < 0 or local_frame_idx >= max_frames:
                        continue
                    for obj_id, (points, labels) in frame_points.items():
                        if len(points) > 0:
                            self.add_points(
                                local_frame_idx=local_frame_idx,
                                obj_id=obj_id,
                                points=points,
                                labels=labels,
                                clear_old=True,
                            )

            # Propagate through frames (ensure correct GPU context)
            video_segments: dict[int, dict[int, np.ndarray]] = {}

            with torch.cuda.device(self.gpu_id):
                for (
                    local_frame_idx,
                    obj_ids,
                    _low_res_masks,
                    video_res_masks,
                    _obj_scores,
                ) in self.predictor.propagate_in_video(
                    self.inference_state,
                    start_frame_idx=0,
                    max_frame_num_to_track=max_frames,
                    reverse=False,
                    propagate_preflight=True,
                ):
                    # Convert local frame index back to original video frame index
                    original_frame_idx = source_frame + local_frame_idx

                    # Scale masks to original resolution
                    video_segments[original_frame_idx] = {}
                    for i, out_obj_id in enumerate(obj_ids):
                        mask = (video_res_masks[i] > 0.0).cpu().numpy()
                        scaled_mask = self._scale_mask_to_original(mask)
                        video_segments[original_frame_idx][out_obj_id] = scaled_mask

                    if callback:
                        progress = (local_frame_idx + 1) / max_frames
                        callback(original_frame_idx, progress)

            # Copy original frames before cleanup
            original_frames = dict(self._original_frames)

            # Clean up to free GPU memory and disk space
            self._reset_inference_state()
            self._cleanup_temp_dir()

            return video_segments, original_frames

    def get_preview_mask(
        self,
        frame_idx: int,
        obj_id: int,
        points: np.ndarray,
        labels: np.ndarray,
    ) -> np.ndarray | None:
        """Get a preview mask for points on a single frame.

        This extracts just one frame for preview purposes.

        Args:
            frame_idx: Frame index in original video
            obj_id: Object ID
            points: Normalized point coordinates
            labels: Point labels

        Returns:
            Mask at original resolution, or None

        Raises:
            RuntimeError: If model not loaded or images directory not set
        """
        if len(points) == 0:
            return None

        # Ensure model is loaded
        if self.model is None or self.predictor is None:
            logger.warning("Model not loaded in get_preview_mask, loading now...")
            self.load_model()
            if self.model is None or self.predictor is None:
                raise RuntimeError("Failed to load SAM3 model")

        # Use inference lock to prevent race conditions where a new request
        # deletes temp files while a previous request's SAM3 init_state is still loading
        with self._inference_lock:
            # For single-frame inference, prepare ONLY the target frame
            # We'll create 3 copies of the same frame to satisfy SAM3's init_state requirements
            # This ensures we always have exactly 3 frames (no gaps) and only use frame 1
            start = frame_idx
            num_frames = 1  # Only prepare the target frame
            local_idx = 0  # Target frame will be at index 0

            logger.debug(
                f"Preparing single frame {frame_idx} for preview (will duplicate to satisfy SAM3)"
            )
            frames_dir = self._prepare_frames_for_propagation(start, num_frames)

            # SAM3's init_state expects at least 3 frames, so duplicate the single frame
            # This ensures we have exactly 000000.jpg, 000001.jpg, 000002.jpg
            if os.path.exists(os.path.join(frames_dir, "000000.jpg")):
                source_frame = os.path.join(frames_dir, "000000.jpg")
                # Create two more copies
                for i in [1, 2]:
                    dest_frame = os.path.join(frames_dir, f"{i:06d}.jpg")
                    if not os.path.exists(dest_frame):
                        try:
                            # Try symlink first
                            os.symlink(os.path.abspath(source_frame), dest_frame)
                        except OSError:
                            # If symlink fails, copy the file
                            shutil.copy2(source_frame, dest_frame)
                logger.debug("Duplicated frame to create 3 frames for SAM3 init_state")
            else:
                raise FileNotFoundError(f"Expected frame 000000.jpg not found in {frames_dir}")

            # Update local_idx to use frame 1 (middle frame) for inference
            local_idx = 1

            self._init_inference_state(frames_dir)

            # Add points and get mask
            mask = self.add_points(
                local_frame_idx=local_idx,
                obj_id=obj_id,
                points=points,
                labels=labels,
                clear_old=True,
            )

            # Clean up to free GPU memory
            self._reset_inference_state()
            self._cleanup_temp_dir()

            return mask

    def get_multi_object_preview(
        self,
        frame_idx: int,
        points_by_obj: dict[int, tuple[np.ndarray, np.ndarray]],
    ) -> dict[int, np.ndarray]:
        """Get preview masks for multiple objects on a single frame.

        Args:
            frame_idx: Frame index
            points_by_obj: Dict of {obj_id: (points, labels)}

        Returns:
            Dict of {obj_id: mask_at_original_resolution}
        """
        if self.images_dir is None:
            raise RuntimeError("No images directory set. Call set_images_dir() first.")

        # Use inference lock to prevent race conditions
        with self._inference_lock:
            # Prepare just a few frames around the target
            start = max(0, frame_idx - 1)
            num_frames = min(3, self.total_frames - start)
            local_idx = frame_idx - start

            frames_dir = self._prepare_frames_for_propagation(start, num_frames)
            self._init_inference_state(frames_dir)

            masks = {}
            for obj_id, (points, labels) in points_by_obj.items():
                if len(points) > 0:
                    mask = self.add_points(
                        local_frame_idx=local_idx,
                        obj_id=obj_id,
                        points=points,
                        labels=labels,
                        clear_old=True,
                    )
                    if mask is not None:
                        masks[obj_id] = mask

            # Clean up to free GPU memory
            self._reset_inference_state()
            self._cleanup_temp_dir()

            return masks

    def get_single_frame_mask(
        self,
        frame_idx: int,
        obj_id: int,
        points: np.ndarray,
        labels: np.ndarray,
    ) -> np.ndarray | None:
        """Get a mask for points on a single frame without video context.

        This is optimized for single-image annotation (manual labeling) where
        we don't need to propagate across a video. Uses SAM3's preview mode
        which loads limited context frames for inference.

        Args:
            frame_idx: Frame index in the images directory (always 0 for single image)
            obj_id: Object ID
            points: Point coordinates [[x, y], ...] (normalized 0-1)
            labels: Point labels [1, 0, ...] (1=positive, 0=negative)

        Returns:
            Mask at original resolution, or None if inference fails
        """
        if len(points) == 0:
            return None

        # Ensure model is loaded
        if self.model is None or self.predictor is None:
            self.load_model()
            if self.model is None or self.predictor is None:
                raise RuntimeError("Failed to load SAM3 model")

        if self.images_dir is None:
            raise RuntimeError("No images directory set. Call set_images_dir() first.")

        if frame_idx >= self.total_frames:
            raise ValueError(f"Frame index {frame_idx} out of range (total: {self.total_frames})")

        # Use get_preview_mask which is designed for single-frame inference
        # It handles frame context loading and inference state setup properly
        return self.get_preview_mask(
            frame_idx=frame_idx,
            obj_id=obj_id,
            points=points,
            labels=labels,
        )

    def cleanup(self) -> None:
        """Clean up all resources."""
        self._reset_inference_state()
        self._cleanup_temp_dir()

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.cleanup()
