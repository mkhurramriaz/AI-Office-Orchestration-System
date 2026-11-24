import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verify root discovery endpoint returns service info."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "TaskFlow AI"
    assert data["status"] == "online"
    assert data["docs_url"] == "/api/v1/docs"
    assert data["health_url"] == "/health"


@pytest.mark.asyncio
async def test_top_level_health_endpoint(async_client: AsyncClient):
    """Verify top-level /health endpoint returns health report structure."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data
    assert "database" in data
    assert "connected" in data["database"]
    assert "latency_ms" in data["database"]


@pytest.mark.asyncio
async def test_api_v1_health_endpoint(async_client: AsyncClient):
    """Verify API v1 /api/v1/health endpoint functions identically."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["app_name"] == "TaskFlow AI"
