"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, labels, projects

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(labels.router, tags=["labels"])
