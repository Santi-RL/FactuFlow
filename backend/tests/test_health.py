"""Tests de health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check básico."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "message" in data


@pytest.mark.asyncio
async def test_health_check_db(client: AsyncClient):
    """Test health check de base de datos."""
    response = await client.get("/api/health/db")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Conexión a la base de datos OK" in data["message"]


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test endpoint raíz."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "FactuFlow API"
    assert data["version"] == "0.1.0"
