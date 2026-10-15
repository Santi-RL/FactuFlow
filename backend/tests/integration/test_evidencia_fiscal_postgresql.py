"""Frontera fiscal y reserva entre procesos en PostgreSQL desechable."""

import os
import subprocess
import sys
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_evidencia_fiscal import (
    test_evidencia_confirmada_antes_de_cae_y_conservada_en_fallos as _verificar_frontera,
)


async def test_postgresql_traslado_v6_preserva_evidencia_exacta(tmp_path):
    from tests.test_evidencia_fiscal_migration import crear_fuente_v6_con_evidencia
    from tests.integration.test_vps_migration_postgresql import (
        _importar_paquete,
        _validar_paquete,
        _write_production_env,
    )
    from app.scripts import vps_migration

    url = require_disposable_postgres_url(purpose="traslado v6 de evidencia fiscal")
    source, certs, expected = crear_fuente_v6_con_evidencia(tmp_path)
    package = vps_migration.export_package(
        source,
        certs,
        tmp_path / "packages",
        "clave-destino-larga",
        source_key_password="clave-v3-sintetica",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.sintetico"
    _write_production_env(env_path)
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    try:
        await _importar_paquete(
            package=package,
            database_url=url,
            env_path=env_path,
            target_certs=tmp_path / "target-certs",
        )
        await _validar_paquete(
            package=package,
            database_url=url,
            env_path=env_path,
            target_certs=tmp_path / "target-certs",
        )
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            attempt = await db.get(IntentoEmisionFiscal, expected[0])
            assert (
                attempt.id,
                attempt.evidencia_json,
                attempt.evidencia_hash,
            ) == expected
    finally:
        await engine.dispose()
        await _reset_schema(url)


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize(
    "fallo",
    [
        None,
        "construccion",
        "timeout",
        "identidad",
        "alteracion",
        "commit_previo",
        "commit_ambiguo",
    ],
)
async def test_postgresql_evidencia_durable_y_fallos(monkeypatch, batch, fallo):
    url = require_disposable_postgres_url(purpose="evidencia previa PF-04/PF-02")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            empresa = Empresa(
                razon_social="Emisor sintético",
                cuit="20123456789",
                condicion_iva="RI",
                domicilio="Calle sintética",
                localidad="Localidad sintética",
                provincia="Provincia sintética",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            db.add(empresa)
            await db.commit()
            await _verificar_frontera(db, empresa, monkeypatch, batch, fallo)
        if fallo is None:
            from app.core.fiscal_storage_legacy import A01_HEAD

            output = _run_alembic("downgrade", A01_HEAD, url, expected_success=False)
            assert "eliminaría evidencia fiscal" in output
    finally:
        await engine.dispose()
        await _reset_schema(url)


async def test_postgresql_dos_procesos_no_reservan_el_mismo_numero():
    url = require_disposable_postgres_url(purpose="reserva fiscal entre procesos")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            empresa = Empresa(
                razon_social="Emisor sintético",
                cuit="20123456789",
                condicion_iva="RI",
                domicilio="Calle sintética",
                localidad="Localidad sintética",
                provincia="Provincia sintética",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            db.add(empresa)
            await db.flush()
            punto = PuntoVenta(
                numero=5, empresa_id=empresa.id, activo=True, es_webservice=True
            )
            db.add(punto)
            await db.commit()
            empresa_id, punto_id = empresa.id, punto.id
        script = '''
import os, sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
url = make_url(os.environ["FACTUFLOW_TEST_POSTGRES_URL"]).set(drivername="postgresql+psycopg2")
engine = create_engine(url)
print("READY", flush=True)
sys.stdin.read(1)
try:
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO intentos_emision_fiscal
            (empresa_id, punto_venta_id, punto_venta_numero, tipo_comprobante,
             numero_planificado, fecha_emision, total, payload_hash, huella_logica,
             estado, created_at, updated_at)
            VALUES (:empresa, :punto, 5, 6, 77, '2026-08-09', '121', :hash, :hash,
                    'en_proceso', now(), now())"""),
            {"empresa": int(sys.argv[1]), "punto": int(sys.argv[2]), "hash": "a" * 64})
    print("reservado", flush=True)
except IntegrityError:
    print("conflicto", flush=True)
finally:
    engine.dispose()
'''
        children = []
        try:
            for _ in range(2):
                children.append(
                    subprocess.Popen(
                        [sys.executable, "-c", script, str(empresa_id), str(punto_id)],
                        env=os.environ.copy(),
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                )
            for child in children:
                assert child.stdout.readline().strip() == "READY"
            for child in children:
                child.stdin.write("g")
                child.stdin.flush()
            results = [child.communicate(timeout=30) for child in children]
            assert sorted(out.strip() for out, _ in results) == [
                "conflicto",
                "reservado",
            ]
            assert all(child.returncode == 0 for child in children)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)
    finally:
        await engine.dispose()
        await _reset_schema(url)
