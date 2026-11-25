from datetime import datetime, timezone
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.database.session import check_db_connection

router = APIRouter()


class DatabaseHealth(BaseModel):
    connected: bool
    message: str
    latency_ms: float = Field(..., description="Query response time in milliseconds")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Overall health status: 'healthy' or 'degraded'")
    app_name: str
    version: str
    environment: str
    timestamp: datetime
    database: DatabaseHealth


@router.get(
    "",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Inspects system status, application version, environment, and database connectivity.",
)
async def get_health_status() -> HealthCheckResponse:
    db_connected, db_message, latency_ms = await check_db_connection()

    overall_status = "healthy" if db_connected else "degraded"

    return HealthCheckResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        database=DatabaseHealth(
            connected=db_connected,
            message=db_message,
            latency_ms=latency_ms,
        ),
    )
