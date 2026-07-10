"""Tests de health check endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.core import database
from app.core.config import settings
from app.core.database import get_db
from app.main import app


class _ProbeFailureSession:
    """Sesión async controlada que falla recién al ejecutar el probe."""

    def __init__(self, error: Exception) -> None:
        """Inicializa la sesión con la excepción esperada."""
        self._error = error

    async def __aenter__(self) -> "_ProbeFailureSession":
        """Entrega la sesión sin adquirir una conexión."""
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        """Finaliza el contexto sin alterar la excepción."""

    async def execute(self, _statement: object) -> None:
        """Falla durante el primer SQL, después del yield de get_db."""
        raise self._error

    async def commit(self) -> None:
        """Simula el commit de la sesión."""

    async def rollback(self) -> None:
        """Simula el rollback de la sesión."""

    async def close(self) -> None:
        """Simula el cierre de la sesión."""


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
async def test_health_db_execute_timeout_lazy_responde_503_y_registra_una_vez(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El timeout del primer SQL debe conservar el contrato y contarse una vez."""
    previous_override = app.dependency_overrides.pop(get_db, None)
    monkeypatch.setattr(
        database,
        "AsyncSessionLocal",
        lambda: _ProbeFailureSession(SQLAlchemyTimeoutError("MARCADOR_DSN_INTERNO")),
    )
    timeout_count_before = database._role_metrics["api"].timeout_count
    try:
        response = await client.get("/api/health/db")
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"
    assert "MARCADOR_DSN_INTERNO" not in response.text
    assert "temporalmente no disponible" in response.json()["detail"]
    assert database._role_metrics["api"].timeout_count == timeout_count_before + 1


@pytest.mark.asyncio
async def test_health_db_execute_operational_error_usa_503_global_sanitizado(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un OperationalError del probe debe llegar al handler global sanitizado."""
    previous_override = app.dependency_overrides.pop(get_db, None)
    monkeypatch.setattr(
        database,
        "AsyncSessionLocal",
        lambda: _ProbeFailureSession(
            OperationalError(
                "SELECT MARCADOR_SQL_INTERNO",
                {},
                RuntimeError("password=secreto"),
            )
        ),
    )
    try:
        response = await client.get("/api/health/db")
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"
    assert "MARCADOR_SQL_INTERNO" not in response.text
    assert "password" not in response.text.lower()
    assert "temporalmente no disponible" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_db_execute_error_no_expone_detalle_interno(
    client: AsyncClient,
) -> None:
    """Un fallo posterior al checkout debe responder sin SQL ni credenciales."""

    class FailingSession:
        """Sesión mínima que falla al ejecutar el probe."""

        async def execute(self, _statement):
            """Simula un error interno después de obtener sesión."""
            raise RuntimeError("MARCADOR_SQL_INTERNO password=secreto")

    async def failing_get_db():
        yield FailingSession()

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = failing_get_db
    try:
        response = await client.get("/api/health/db")
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 503
    assert "MARCADOR_SQL_INTERNO" not in response.text
    assert "password" not in response.text.lower()
    assert response.json()["detail"] == (
        "No se pudo verificar la conexión a la base de datos."
    )


@pytest.mark.asyncio
async def test_health_worker_requiere_autenticacion(
    client: AsyncClient,
) -> None:
    """El diagnóstico interno no debe ser público."""
    response = await client.get("/api/health/worker")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_worker_sin_token_no_adquiere_conexion_api(
    client: AsyncClient,
) -> None:
    """Rechazar credenciales ausentes no debe ocupar el pool API."""
    previous_override = app.dependency_overrides.pop(get_db, None)
    before = database._role_metrics["api"].acquisition_count
    try:
        response = await client.get("/api/health/worker")
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_db] = previous_override

    assert response.status_code == 403
    assert database._role_metrics["api"].acquisition_count == before


@pytest.mark.asyncio
async def test_health_worker_rechaza_usuario_no_admin(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    """Un usuario autenticado común no puede inspeccionar pools."""
    response = await client.get("/api/health/worker", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_worker_admin_expone_solo_allowlist(
    client: AsyncClient,
    admin_auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El administrador recibe métricas tipadas sin campos internos extra."""
    runtime = {
        "estado": "esperando",
        "habilitado": True,
        "ejecutando": True,
        "ocupado": False,
        "ciclo_iniciado_at": "2026-07-10T10:00:00",
        "ciclo_finalizado_at": "2026-07-10T10:00:01",
        "ultima_duracion_ms": 1000.0,
        "ultimo_resultado": "exitoso",
        "ultimo_exito_at": "2026-07-10T10:00:01",
        "ultimo_error_at": None,
        "stale_detectados_ultimo_ciclo": 0,
        "lotes_en_cola_ultimo_ciclo": 2,
        "lotes_procesados_ultimo_ciclo": 2,
        "mensaje_error": "DATO_SENSIBLE_TEST",
        "cae": "DATO_SENSIBLE_TEST",
    }
    pool_role = {
        "pool_size": 2,
        "max_overflow": 1,
        "capacity": 3,
        "checked_out": 1,
        "checked_in": 1,
        "overflow": 0,
        "high_water_mark": 1,
        "acquisition_count": 10,
        "timeout_count": 0,
        "last_wait_ms": 0.5,
        "max_wait_ms": 1.25,
        "database_url": "DATO_SENSIBLE_TEST",
    }
    pools = {
        "separation_required": True,
        "separated": True,
        "api": dict(pool_role),
        "worker": dict(pool_role),
        "credentials": "DATO_SENSIBLE_TEST",
    }
    monkeypatch.setattr(
        "app.api.health.get_lote_worker_status",
        lambda _app: runtime,
    )
    monkeypatch.setattr(
        "app.api.health.get_database_pool_status",
        lambda: pools,
    )

    response = await client.get(
        "/api/health/worker",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"status", "worker", "pools"}
    assert data["status"] == "healthy"
    assert set(data["worker"]) == {
        "estado",
        "habilitado",
        "ejecutando",
        "ocupado",
        "ciclo_iniciado_at",
        "ciclo_finalizado_at",
        "ultima_duracion_ms",
        "ultimo_resultado",
        "ultimo_exito_at",
        "ultimo_error_at",
        "stale_detectados_ultimo_ciclo",
        "lotes_en_cola_ultimo_ciclo",
        "lotes_procesados_ultimo_ciclo",
    }
    assert set(data["pools"]) == {
        "separation_required",
        "separated",
        "api",
        "worker",
    }
    assert set(data["pools"]["api"]) == {
        "pool_size",
        "max_overflow",
        "capacity",
        "checked_out",
        "checked_in",
        "overflow",
        "high_water_mark",
        "acquisition_count",
        "timeout_count",
        "last_wait_ms",
        "max_wait_ms",
    }
    assert "DATO_SENSIBLE_TEST" not in response.text
    assert "mensaje_error" not in response.text
    assert "database_url" not in response.text
    assert "credentials" not in response.text


@pytest.mark.asyncio
async def test_health_worker_sqlite_compartido_es_topologia_sana(
    client: AsyncClient,
    admin_auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQLite no requiere separar el engine API del worker."""
    runtime = {
        "estado": "esperando",
        "habilitado": True,
        "ejecutando": True,
        "ocupado": False,
        "ciclo_iniciado_at": None,
        "ciclo_finalizado_at": None,
        "ultima_duracion_ms": None,
        "ultimo_resultado": "exitoso",
        "ultimo_exito_at": None,
        "ultimo_error_at": None,
        "stale_detectados_ultimo_ciclo": 0,
        "lotes_en_cola_ultimo_ciclo": 0,
        "lotes_procesados_ultimo_ciclo": 0,
    }
    monkeypatch.setattr(
        "app.api.health.get_lote_worker_status",
        lambda _app: runtime,
    )

    response = await client.get(
        "/api/health/worker",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "healthy"
    assert data["pools"]["separation_required"] is False
    assert data["pools"]["separated"] is False


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test endpoint raíz."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "FactuFlow API"
    assert data["version"] == settings.app_version
