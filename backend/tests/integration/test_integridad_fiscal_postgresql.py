"""Integración PostgreSQL desechable para la integridad fiscal PF-01B."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


BACKEND_DIR = Path(__file__).resolve().parents[2]
REVISION_ANTERIOR_INTEGRIDAD_FISCAL = "f7a8b9c0d1e2"
REVISION_INTEGRIDAD_FISCAL = "a8b9c0d1e2f3"
ESTADOS_INTENTO_FISCAL = (
    "autorizado",
    "en_proceso",
    "fallido_verificado",
    "rechazado_arca",
    "requiere_reconciliacion",
)
ESTADOS_COMPROBANTE = ("autorizado", "borrador", "pendiente", "rechazado")
CAE_SINTETICO = "12345678901234"
FECHA_SINTETICA = date(2026, 7, 13)
SCHEMA_RESET_ENV = "FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET"
NOMBRES_DESCARTABLES = ("test", "tmp", "temp", "pf01b")


def _postgres_url() -> str:
    """Valida la URL y el opt-in destructivo de PostgreSQL desechable."""
    configured_url = os.getenv("FACTUFLOW_TEST_POSTGRES_URL", "").strip()
    if not configured_url:
        pytest.skip("Requiere PostgreSQL desechable explícito para PF-01B")

    if configured_url.startswith("postgresql://"):
        configured_url = configured_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    if not configured_url.startswith("postgresql+asyncpg://"):
        pytest.fail("FACTUFLOW_TEST_POSTGRES_URL debe apuntar a PostgreSQL")

    if os.getenv(SCHEMA_RESET_ENV, "").strip() != "1":
        pytest.fail(
            f"{SCHEMA_RESET_ENV}=1 es obligatorio porque la prueba recrea "
            "el schema public"
        )

    database_name = (make_url(configured_url).database or "").lower()
    if not any(marker in database_name for marker in NOMBRES_DESCARTABLES):
        pytest.fail(
            "La base desechable debe incluir test, tmp, temp o pf01b en su nombre"
        )
    return configured_url


def test_postgresql_guard_requiere_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El harness falla antes de conectar si no existe opt-in destructivo."""
    monkeypatch.setenv(
        "FACTUFLOW_TEST_POSTGRES_URL",
        "postgresql+asyncpg://user@127.0.0.1/factuflow_pf01b_test",
    )
    monkeypatch.delenv(SCHEMA_RESET_ENV, raising=False)

    with pytest.raises(pytest.fail.Exception, match=SCHEMA_RESET_ENV):
        _postgres_url()


def test_postgresql_guard_rechaza_nombre_operativo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El harness rechaza nombres que no declaran una base descartable."""
    monkeypatch.setenv(
        "FACTUFLOW_TEST_POSTGRES_URL",
        "postgresql+asyncpg://user@127.0.0.1/factuflow",
    )
    monkeypatch.setenv(SCHEMA_RESET_ENV, "1")

    with pytest.raises(pytest.fail.Exception, match="base desechable"):
        _postgres_url()


def _run_alembic(
    action: str,
    revision: str,
    database_url: str,
    *,
    expected_success: bool = True,
) -> str:
    """Ejecuta Alembic contra PostgreSQL sin imprimir la URL ni credenciales."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "testing"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", action, revision],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if expected_success:
        assert result.returncode == 0, output
    else:
        assert result.returncode != 0
    return output


async def _reset_schema(database_url: str) -> None:
    """Recrea el schema público de la base exclusivamente desechable."""
    engine = create_async_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


async def _crear_contexto_sintetico(engine: AsyncEngine) -> None:
    """Inserta un emisor y punto de venta ficticios."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO empresas (
                    id, razon_social, cuit, condicion_iva, domicilio,
                    localidad, provincia, codigo_postal, inicio_actividades,
                    created_at, updated_at
                ) VALUES (
                    1, :razon_social, :cuit, :condicion_iva, :domicilio,
                    :localidad, :provincia, :codigo_postal,
                    :inicio_actividades, now(), now()
                )
                """
            ),
            {
                "razon_social": "Emisor sintético",
                "cuit": "20000000001",
                "condicion_iva": "RI",
                "domicilio": "Domicilio sintético",
                "localidad": "Localidad sintética",
                "provincia": "Provincia sintética",
                "codigo_postal": "1000",
                "inicio_actividades": date(2020, 1, 1),
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO puntos_venta (
                    id, numero, nombre, es_webservice, bloqueado, activo,
                    empresa_id, created_at
                ) VALUES (
                    1, 41, :nombre, true, false, true, 1, now()
                )
                """
            ),
            {"nombre": "Punto sintético"},
        )


def _intento_params(
    row_id: int,
    estado: str,
    numero_planificado: int | None,
) -> dict[str, object]:
    """Construye parámetros sintéticos para un intento fiscal."""
    return {
        "id": row_id,
        "tipo_comprobante": 6,
        "punto_venta_numero": 41,
        "numero_planificado": numero_planificado,
        "fecha_emision": FECHA_SINTETICA,
        "total": Decimal("121.00"),
        "payload_hash": f"{row_id:064d}",
        "huella_logica": f"{row_id + 1:064d}",
        "estado": estado,
        "empresa_id": 1,
        "punto_venta_id": 1,
    }


INTENTO_INSERT = text(
    """
    INSERT INTO intentos_emision_fiscal (
        id, tipo_comprobante, punto_venta_numero, numero_planificado,
        fecha_emision, total, payload_hash, huella_logica, estado,
        created_at, updated_at, empresa_id, punto_venta_id
    ) VALUES (
        :id, :tipo_comprobante, :punto_venta_numero, :numero_planificado,
        :fecha_emision, :total, :payload_hash, :huella_logica, :estado,
        now(), now(), :empresa_id, :punto_venta_id
    )
    """
)


def _comprobante_params(
    row_id: int,
    estado: str,
    *,
    cae: str | None,
    cae_vencimiento: date | None,
) -> dict[str, object]:
    """Construye parámetros sintéticos para un comprobante."""
    return {
        "id": row_id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "numero": 200 + row_id,
        "fecha_emision": FECHA_SINTETICA,
        "subtotal": Decimal("100.00"),
        "descuento": Decimal("0.00"),
        "iva_21": Decimal("21.00"),
        "iva_10_5": Decimal("0.00"),
        "iva_27": Decimal("0.00"),
        "otros_impuestos": Decimal("0.00"),
        "total": Decimal("121.00"),
        "cae": cae,
        "cae_vencimiento": cae_vencimiento,
        "estado": estado,
        "moneda": "PES",
        "cotizacion": Decimal("1.000000"),
        "empresa_id": 1,
        "punto_venta_id": 1,
    }


COMPROBANTE_INSERT = text(
    """
    INSERT INTO comprobantes (
        id, tipo_comprobante, concepto, numero, fecha_emision, subtotal,
        descuento, iva_21, iva_10_5, iva_27, otros_impuestos, total,
        cae, cae_vencimiento, estado, moneda, cotizacion, empresa_id,
        punto_venta_id, created_at, updated_at
    ) VALUES (
        :id, :tipo_comprobante, :concepto, :numero, :fecha_emision,
        :subtotal, :descuento, :iva_21, :iva_10_5, :iva_27,
        :otros_impuestos, :total, :cae, :cae_vencimiento, :estado,
        :moneda, :cotizacion, :empresa_id, :punto_venta_id, now(), now()
    )
    """
)


async def _insertar_intento(
    engine: AsyncEngine,
    row_id: int,
    estado: str,
    numero_planificado: int | None,
) -> None:
    """Persiste un intento sintético en una transacción propia."""
    async with engine.begin() as connection:
        await connection.execute(
            INTENTO_INSERT,
            _intento_params(row_id, estado, numero_planificado),
        )


async def _insertar_comprobante(
    engine: AsyncEngine,
    row_id: int,
    estado: str,
    *,
    cae: str | None,
    cae_vencimiento: date | None,
) -> None:
    """Persiste un comprobante sintético en una transacción propia."""
    async with engine.begin() as connection:
        await connection.execute(
            COMPROBANTE_INSERT,
            _comprobante_params(
                row_id,
                estado,
                cae=cae,
                cae_vencimiento=cae_vencimiento,
            ),
        )


async def _constraint_names(engine: AsyncEngine) -> set[str]:
    """Devuelve los nombres de checks fiscales presentes."""
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid IN (
                    'intentos_emision_fiscal'::regclass,
                    'comprobantes'::regclass
                )
                AND contype = 'c'
                """
            )
        )
    return {str(row[0]) for row in result}


async def _alembic_version(engine: AsyncEngine) -> str:
    """Devuelve la revisión Alembic aplicada."""
    async with engine.connect() as connection:
        value = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert value is not None
    return str(value)


async def _indice_reserva_definicion(engine: AsyncEngine) -> str:
    """Devuelve la definición PostgreSQL del índice de reserva activa."""
    async with engine.connect() as connection:
        value = await connection.scalar(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'intentos_emision_fiscal'
                AND indexname = 'uq_intentos_emision_fiscal_reserva_activa'
                """
            )
        )
    assert value is not None
    return str(value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_integridad_fiscal_constraints_y_concurrencia() -> None:
    """Valida migración, dominios, CAE y exclusión concurrente en PostgreSQL."""
    database_url = _postgres_url()
    await _reset_schema(database_url)
    _run_alembic(
        "upgrade",
        REVISION_ANTERIOR_INTEGRIDAD_FISCAL,
        database_url,
    )

    engine = create_async_engine(database_url)
    await _crear_contexto_sintetico(engine)
    await _insertar_intento(engine, 1, "en_proceso", 101)
    await _insertar_comprobante(
        engine,
        1,
        "autorizado",
        cae=CAE_SINTETICO,
        cae_vencimiento=FECHA_SINTETICA,
    )
    await engine.dispose()

    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    engine = create_async_engine(database_url)
    expected_constraints = {
        "ck_intentos_emision_fiscal_estado_valido",
        "ck_comprobantes_estado_valido",
        "ck_comprobantes_estado_cae_coherente",
    }
    assert expected_constraints <= await _constraint_names(engine)
    index_definition = await _indice_reserva_definicion(engine)
    assert "UNIQUE INDEX" in index_definition
    assert "numero_planificado IS NOT NULL" in index_definition

    for offset, estado in enumerate(ESTADOS_INTENTO_FISCAL, start=10):
        await _insertar_intento(engine, offset, estado, 300 + offset)

    await _insertar_intento(engine, 30, "fallido_verificado", 700)
    await _insertar_intento(engine, 31, "en_proceso", 700)
    await _insertar_intento(engine, 32, "rechazado_arca", 701)
    await _insertar_intento(engine, 33, "autorizado", 701)

    with pytest.raises(IntegrityError):
        await _insertar_intento(engine, 40, "estado_inexistente", 740)

    for offset, estado in enumerate(ESTADOS_COMPROBANTE, start=10):
        autorizado = estado == "autorizado"
        await _insertar_comprobante(
            engine,
            offset,
            estado,
            cae=CAE_SINTETICO if autorizado else None,
            cae_vencimiento=FECHA_SINTETICA if autorizado else None,
        )

    with pytest.raises(IntegrityError):
        await _insertar_comprobante(
            engine,
            40,
            "estado_inexistente",
            cae=None,
            cae_vencimiento=None,
        )
    with pytest.raises(IntegrityError):
        await _insertar_comprobante(
            engine,
            41,
            "autorizado",
            cae=None,
            cae_vencimiento=FECHA_SINTETICA,
        )
    with pytest.raises(IntegrityError):
        await _insertar_comprobante(
            engine,
            42,
            "pendiente",
            cae=CAE_SINTETICO,
            cae_vencimiento=None,
        )

    first_connection = await engine.connect()
    first_transaction = await first_connection.begin()
    try:
        await first_connection.execute(
            INTENTO_INSERT,
            _intento_params(50, "en_proceso", 900),
        )

        async def _insertar_reserva_competidora() -> None:
            """Intenta reservar el mismo número desde otra transacción."""
            async with engine.begin() as second_connection:
                await second_connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                await second_connection.execute(
                    INTENTO_INSERT,
                    _intento_params(
                        51,
                        "requiere_reconciliacion",
                        900,
                    ),
                )

        competing_task = asyncio.create_task(_insertar_reserva_competidora())
        await asyncio.sleep(0.2)
        assert not competing_task.done()
        await first_transaction.commit()

        with pytest.raises(IntegrityError):
            await asyncio.wait_for(competing_task, timeout=5)
    finally:
        if first_transaction.is_active:
            await first_transaction.rollback()
        await first_connection.close()

    await engine.dispose()
    _run_alembic(
        "downgrade",
        REVISION_ANTERIOR_INTEGRIDAD_FISCAL,
        database_url,
    )
    engine = create_async_engine(database_url)
    assert not expected_constraints & await _constraint_names(engine)
    assert await _alembic_version(engine) == REVISION_ANTERIOR_INTEGRIDAD_FISCAL
    assert "UNIQUE INDEX" in await _indice_reserva_definicion(engine)
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_preflight_bloquea_datos_ambiguos() -> None:
    """El preflight PostgreSQL aborta sin instalar checks ni ocultar conflictos."""
    database_url = _postgres_url()
    await _reset_schema(database_url)
    _run_alembic(
        "upgrade",
        REVISION_ANTERIOR_INTEGRIDAD_FISCAL,
        database_url,
    )

    engine = create_async_engine(database_url)
    await _crear_contexto_sintetico(engine)
    await _insertar_intento(engine, 1, "estado_inexistente", None)
    await _insertar_comprobante(
        engine,
        1,
        "estado_inexistente",
        cae=None,
        cae_vencimiento=None,
    )
    await _insertar_comprobante(
        engine,
        2,
        "autorizado",
        cae=None,
        cae_vencimiento=FECHA_SINTETICA,
    )
    await _insertar_comprobante(
        engine,
        3,
        "pendiente",
        cae=CAE_SINTETICO,
        cae_vencimiento=None,
    )
    async with engine.begin() as connection:
        await connection.execute(
            text("DROP INDEX uq_intentos_emision_fiscal_reserva_activa")
        )
    await _insertar_intento(engine, 2, "en_proceso", 800)
    await _insertar_intento(
        engine,
        3,
        "requiere_reconciliacion",
        800,
    )
    await engine.dispose()

    output = _run_alembic(
        "upgrade",
        REVISION_INTEGRIDAD_FISCAL,
        database_url,
        expected_success=False,
    )
    expected_categories = {
        "intentos_estado_desconocido=1",
        "comprobantes_estado_desconocido=1",
        "comprobantes_autorizados_incompletos=1",
        "comprobantes_no_autorizados_con_cae=1",
        "reservas_activas_duplicadas=1",
    }
    assert all(category in output for category in expected_categories)

    engine = create_async_engine(database_url)
    assert await _alembic_version(engine) == REVISION_ANTERIOR_INTEGRIDAD_FISCAL
    assert not {
        "ck_intentos_emision_fiscal_estado_valido",
        "ck_comprobantes_estado_valido",
        "ck_comprobantes_estado_cae_coherente",
    } & await _constraint_names(engine)
    await engine.dispose()
