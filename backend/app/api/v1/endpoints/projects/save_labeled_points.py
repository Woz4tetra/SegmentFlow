from uuid import UUID
import asyncio
from pathlib import Path
import numpy as np
import cv2

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import LabeledPointResponse, SaveLabeledPointsRequest
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.sam3_state import get_primary_tracker
from app.core.config import settings
from app.models.image import Image
from app.models.label import Label
from app.models.labeled_point import LabeledPoint
from app.models.mask import Mask
from app.models.project import Project

from .shared_objects import router

logger = get_logger(__name__)


async def _run_sam_inference_and_save_mask(
    db: AsyncSession | None,
    project_id: UUID,
    frame_number: int,
    label_id: UUID,
    points: list[tuple[float, float]],
    labels: list[int],
) -> bool:
    """Run SAM inference on the given points and save the resulting mask.
    
    Args:
        db: Database session (if None, a new session will be created)
        project_id: Project UUID
        frame_number: Frame number (0-indexed)
        label_id: Label UUID
        points: List of (x, y) coordinate tuples (normalized 0-1)
        labels: List of labels (1=include, 0=exclude) for each point
        
    Returns:
        True if mask was successfully saved, False otherwise
    """
    # Create a new database session if one wasn't provided
    # (needed for background tasks since request context session will be closed)
    if db is None:
        async for db in get_db():
            return await _run_sam_inference_and_save_mask(
                db=db,
                project_id=project_id,
                frame_number=frame_number,
                label_id=label_id,
                points=points,
                labels=labels,
            )
        return False
    try:
        # Get SAM3 tracker
        tracker = get_primary_tracker()
        if tracker is None:
            logger.warning("SAM3 tracker not initialized, skipping mask generation")
            return False
        
        # Ensure model is loaded
        if tracker.model is None or tracker.predictor is None:
            logger.warning("SAM3 model not loaded, attempting to load...")
            try:
                tracker.load_model()
            except Exception as e:
                logger.error(f"Failed to load SAM3 model: {e}")
                return False
        
        # Get project and image
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            logger.error(f"Project not found: {project_id}")
            return False
        
        image_result = await db.execute(
            select(Image).where(
                Image.project_id == project_id,
                Image.frame_number == frame_number,
            )
        )
        image = image_result.scalar_one_or_none()
        if not image:
            logger.error(f"Image not found for frame {frame_number}")
            return False
        
        # Get inference directory
        project_dir = Path(settings.PROJECTS_ROOT_DIR) / str(project.id)
        inference_dir = project_dir / "inference"
        if not inference_dir.exists():
            logger.error(f"Inference directory not found: {inference_dir}")
            return False
        
        # Set images directory for tracker
        tracker.set_images_dir(str(inference_dir))
        
        # Convert points and labels to numpy arrays
        points_array = np.array(points, dtype=np.float32)
        labels_array = np.array(labels, dtype=np.int32)
        
        # Run single-frame inference without video context
        # For manual labeling, we only need to segment the current frame
        loop = asyncio.get_event_loop()
        mask = await loop.run_in_executor(
            None,
            tracker.get_single_frame_mask,
            frame_number,  # Use actual frame number from the inference directory
            hash(str(label_id)) % (2**31),  # Use positive hash as obj_id (SAM expects int32)
            points_array,
            labels_array,
        )
        
        if mask is None:
            logger.warning(f"SAM inference returned None for frame {frame_number}")
            return False
        
        # Ensure mask is a 2D array and contiguous in memory for OpenCV
        if mask.ndim > 2:
            # If mask is 3D, take the first channel or squeeze
            mask = np.squeeze(mask)
        if mask.ndim != 2:
            logger.warning(f"Unexpected mask shape {mask.shape}")
            return False
        
        # Convert mask to uint8 and ensure it's contiguous (required by OpenCV)
        mask_uint8 = (mask * 255).astype(np.uint8) if mask.dtype != np.uint8 else mask.astype(np.uint8)
        mask_uint8 = np.ascontiguousarray(mask_uint8)
        
        # Find contours using OpenCV with CHAIN_APPROX_SIMPLE to reduce point count
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            logger.warning(f"SAM mask has no contours for frame {frame_number}")
            return False
        
        # Take only the largest contour (avoid multiple disconnected regions)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Reshape contour from (n, 1, 2) to list of [x, y] pairs
        contour_pixels = largest_contour.reshape(-1, 2).tolist()
        
        if len(contour_pixels) < 3:
            logger.warning(f"SAM mask contour too small for frame {frame_number}")
            return False
        
        # Calculate actual mask area
        area = float(cv2.contourArea(largest_contour))
        
        # Check if mask already exists for this label
        existing_mask_result = await db.execute(
            select(Mask).where(
                Mask.image_id == image.id,
                Mask.label_id == label_id,
            )
        )
        existing_mask = existing_mask_result.scalar_one_or_none()
        
        if existing_mask:
            # Update existing mask
            existing_mask.contour_polygon = contour_pixels
            existing_mask.area = area
            db.add(existing_mask)
        else:
            # Create new mask
            db_mask = Mask(
                image_id=image.id,
                label_id=label_id,
                contour_polygon=contour_pixels,
                area=area,
            )
            db.add(db_mask)
        
        await db.commit()
        logger.info(
            f"Successfully saved SAM mask for project {project_id}, "
            f"frame {frame_number}, label {label_id} with {area} pixels"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error running SAM inference: {e}", exc_info=True)
        return False


@router.post(
    "/projects/{project_id}/frames/{frame_number}/points",
    response_model=list[LabeledPointResponse],
    status_code=status.HTTP_201_CREATED,
)
async def save_labeled_points(
    project_id: UUID,
    frame_number: int,
    request: SaveLabeledPointsRequest,
    db: AsyncSession = Depends(get_db),
) -> list[LabeledPointResponse]:
    """Save labeled points for a specific frame.

    Args:
        project_id: ID of the project
        frame_number: Frame number (0-indexed)
        request: Points to save
        db: Database session dependency

    Returns:
        list[LabeledPointResponse]: List of saved points

    Raises:
        HTTPException: If project, image, or label not found
    """
    try:
        # Verify project exists
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found",
            )

        # Get image for this frame
        image_result = await db.execute(
            select(Image).where(
                Image.project_id == project_id,
                Image.frame_number == frame_number,
            )
        )
        image = image_result.scalar_one_or_none()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image not found for frame {frame_number}",
            )

        # Verify label exists
        label_result = await db.execute(select(Label).where(Label.id == request.label_id))
        label = label_result.scalar_one_or_none()
        if not label:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Label with ID {request.label_id} not found",
            )

        # Delete existing points for this image and label
        existing_points_result = await db.execute(
            select(LabeledPoint).where(
                LabeledPoint.image_id == image.id,
                LabeledPoint.label_id == request.label_id,
            )
        )
        existing_points = existing_points_result.scalars().all()
        for point in existing_points:
            await db.delete(point)

        # Create new points
        saved_points = []
        for point_data in request.points:
            db_point = LabeledPoint(
                image_id=image.id,
                label_id=request.label_id,
                x=point_data.x,
                y=point_data.y,
                include=point_data.include,
            )
            db.add(db_point)
            saved_points.append(db_point)

        # Mark image as manually labeled
        image.manually_labeled = True
        db.add(image)

        await db.commit()

        # Run SAM inference asynchronously to generate and save mask
        # Extract coordinates and labels from saved points
        points_list = [(p.x, p.y) for p in saved_points]
        labels_list = [1 if p.include else 0 for p in saved_points]
        
        logger.info(
            f"Running SAM inference for project {project_id}, frame {frame_number}, "
            f"label {request.label_id} with {len(points_list)} points"
        )
        
        # Run SAM inference in background (don't wait for result)
        # This allows the API to return quickly while SAM processes
        # Note: We don't pass the request db session since it will be closed.
        # The background task will create its own session.
        asyncio.create_task(
            _run_sam_inference_and_save_mask(
                db=None,  # Background task will create its own session
                project_id=project_id,
                frame_number=frame_number,
                label_id=request.label_id,
                points=points_list,
                labels=labels_list,
            )
        )

        return [LabeledPointResponse.model_validate(p) for p in saved_points]

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save labeled points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save labeled points: {e!s}",
        ) from e

