from fastapi import APIRouter

from app.api.v1.endpoints import ai, auth, health, notifications, projects, tasks, users, workflows

api_router = APIRouter()

api_router.include_router(ai.router, prefix="/ai", tags=["AI Co-Pilot"])
api_router.include_router(workflows.router, prefix="/ai/workflows", tags=["AI Workflows"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
