import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Ensure backend root is in sys.path regardless of execution working directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.endpoints.health import get_health_status
from app.api.v1.router import api_router
from app.core.config import settings
from app.database.session import engine

logger = logging.getLogger("taskflow.backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    logger.info("Initializing %s v%s...", settings.PROJECT_NAME, settings.VERSION)
    yield
    logger.info("Disposing database connection pool...")
    await engine.dispose()
    logger.info("Shutdown completed.")


def create_application() -> FastAPI:
    """Factory function for creating and configuring the FastAPI application."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="TaskFlow AI — Full-Stack AI-Powered Office Project Orchestration System",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Exception Handling
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                },
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Request validation failed",
                    "details": exc.errors(),
                },
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                },
            },
        )

    # Include API v1 router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Top-level health check endpoint for cloud load balancers and orchestrators
    application.add_api_route(
        "/health",
        get_health_status,
        methods=["GET"],
        tags=["Health"],
        include_in_schema=True,
    )

    @application.get(
        "/",
        tags=["Root"],
        summary="Service Info",
        description="Root discovery endpoint returning application metadata and documentation links.",
    )
    async def root_info() -> JSONResponse:
        return JSONResponse(
            content={
                "name": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "status": "online",
                "docs_url": f"{settings.API_V1_STR}/docs",
                "health_url": "/health",
            }
        )

    return application


app = create_application()
