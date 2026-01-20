"""Project label enable/disable settings endpoints."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    ProjectLabelSettingResponse,
    ProjectLabelSettingUpdate,
)
from app.core.database import get_db
from app.models.label import Label
from app.models.project import Project
from app.models.project_label_setting import ProjectLabelSetting

from .shared_objects import router


@router.get(
    "/projects/{project_id}/label_settings",
    response_model=list[ProjectLabelSettingResponse],
)
async def list_project_label_settings(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ProjectLabelSettingResponse]:
    """List labels for a project with enabled flags."""
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if project_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    label_result = await db.execute(select(Label).order_by(Label.created_at))
    labels = label_result.scalars().all()

    settings_result = await db.execute(
        select(ProjectLabelSetting).where(ProjectLabelSetting.project_id == project_id)
    )
    settings = settings_result.scalars().all()
    enabled_by_label = {setting.label_id: setting.enabled for setting in settings}

    return [
        ProjectLabelSettingResponse(
            id=label.id,
            name=label.name,
            color_hex=label.color_hex,
            thumbnail_path=label.thumbnail_path,
            enabled=enabled_by_label.get(label.id, False),
        )
        for label in labels
    ]


@router.patch(
    "/projects/{project_id}/label_settings/{label_id}",
    response_model=ProjectLabelSettingResponse,
)
async def update_project_label_setting(
    project_id: UUID,
    label_id: UUID,
    payload: ProjectLabelSettingUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectLabelSettingResponse:
    """Update a single label's enabled flag for a project."""
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if project_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    label_result = await db.execute(select(Label).where(Label.id == label_id))
    label = label_result.scalar_one_or_none()
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label with ID {label_id} not found",
        )

    setting_result = await db.execute(
        select(ProjectLabelSetting).where(
            ProjectLabelSetting.project_id == project_id,
            ProjectLabelSetting.label_id == label_id,
        )
    )
    setting = setting_result.scalar_one_or_none()

    if setting is None:
        setting = ProjectLabelSetting(
            project_id=project_id,
            label_id=label_id,
            enabled=payload.enabled,
        )
        db.add(setting)
    else:
        setting.enabled = payload.enabled
        db.add(setting)

    try:
        await db.commit()
        await db.refresh(setting)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update label settings: {e!s}",
        ) from e

    return ProjectLabelSettingResponse(
        id=label.id,
        name=label.name,
        color_hex=label.color_hex,
        thumbnail_path=label.thumbnail_path,
        enabled=setting.enabled,
    )
