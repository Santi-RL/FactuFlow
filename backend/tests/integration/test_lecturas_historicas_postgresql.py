"""Vínculo, compactación y lectores concurrentes en PostgreSQL desechable."""

from datetime import date

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.services.lecturas_historicas_service import cargar_lecturas_historicas
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_lecturas_historicas import crear_historia, verificar_compactacion


@pytest.mark.parametrize("batch", [False, True])
async def test_postgresql_historia_concurrente_y_compactacion(monkeypatch, batch):
    url = require_disposable_postgres_url(purpose="lecturas históricas PF-04/PF-02")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    sesiones = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sesiones() as db:
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
            if batch:
                await verificar_compactacion(db, empresa, monkeypatch)
            else:
                await crear_historia(db, empresa, monkeypatch)
        async with sesiones() as lector, sesiones() as escritor:
            comps = list(
                await lector.scalars(
                    select(Comprobante).options(
                        joinedload(Comprobante.empresa),
                        joinedload(Comprobante.punto_venta),
                    )
                )
            )
            antes = await cargar_lecturas_historicas(lector, comps)
            await escritor.execute(
                update(Empresa).values(
                    razon_social="Ficha concurrente", cuit="20999999999"
                )
            )
            await escritor.execute(update(PuntoVenta).values(numero=99))
            await escritor.commit()
            # Una sesión nueva y la sesión que ya leía observan la misma historia.
            assert antes == await cargar_lecturas_historicas(lector, comps)
        async with sesiones() as reiniciado:
            comps = list(
                await reiniciado.scalars(
                    select(Comprobante).options(
                        joinedload(Comprobante.empresa),
                        joinedload(Comprobante.punto_venta),
                    )
                )
            )
            assert antes == await cargar_lecturas_historicas(reiniciado, comps)
            assert all(c.punto_venta.numero == 99 for c in comps)
            assert all(lectura.punto_venta_numero == 5 for lectura in antes.values())
            assert (
                not reiniciado.new and not reiniciado.dirty and not reiniciado.deleted
            )
    finally:
        await engine.dispose()
        await _reset_schema(url)


async def test_v6_sqlite_postgresql_conserva_lecturas_individual_y_masiva(
    tmp_path, monkeypatch
):
    from app.scripts import vps_migration
    from tests.test_evidencia_fiscal_migration import crear_fuente_v6_con_evidencia
    from tests.integration.test_vps_migration_postgresql import (
        _importar_paquete,
        _validar_paquete,
        _write_production_env,
    )

    url = require_disposable_postgres_url(purpose="traslado de lecturas históricas v6")
    source, certs, _ = crear_fuente_v6_con_evidencia(tmp_path)
    sqlite = create_async_engine(f"sqlite+aiosqlite:///{source.as_posix()}")
    try:
        async with async_sessionmaker(sqlite, expire_on_commit=False)() as db:
            empresa = (await db.scalars(select(Empresa))).first()
            _, punto = await crear_historia(
                db, empresa, monkeypatch, terminar_operacion=True
            )
            # El helper de emisión prepara sólo el ambiente que usa. Un paquete
            # completo también conserva la cabeza inicial no verificada del otro.
            from app.models.elegibilidad_rece import (
                PuntoVentaElegibilidadReceActual,
                PuntoVentaElegibilidadReceRevision,
            )
            from datetime import datetime

            revision = PuntoVentaElegibilidadReceRevision(
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                ambiente="homologacion",
                revision=1,
                estado="no_verificado",
                fuente="alta_manual",
                evidencia_tipo="sin_evidencia",
                punto_revision_fiscal=1,
                observado_en=datetime(2026, 8, 9, 12),
            )
            db.add(revision)
            await db.flush()
            db.add(
                PuntoVentaElegibilidadReceActual(
                    empresa_id=empresa.id,
                    punto_venta_id=punto.id,
                    ambiente="homologacion",
                    revision_actual_id=revision.id,
                )
            )
            await db.commit()
            comps = list(
                await db.scalars(
                    select(Comprobante).options(
                        joinedload(Comprobante.empresa),
                        joinedload(Comprobante.punto_venta),
                    )
                )
            )
            antes = await cargar_lecturas_historicas(db, comps)
            intentos = list(
                await db.scalars(
                    select(IntentoEmisionFiscal).where(
                        IntentoEmisionFiscal.evidencia_json.is_not(None)
                    )
                )
            )
            assert {i.lote_id is None for i in intentos} == {False, True}
            assert all(
                antes[i.comprobante_id].origen == "evidencia_previa" for i in intentos
            )
            assert any(lectura.cobertura == "ausente" for lectura in antes.values())
    finally:
        await sqlite.dispose()
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
            comps = list(
                await db.scalars(
                    select(Comprobante).options(
                        joinedload(Comprobante.empresa),
                        joinedload(Comprobante.punto_venta),
                    )
                )
            )
            assert antes == await cargar_lecturas_historicas(db, comps)
    finally:
        await engine.dispose()
        await _reset_schema(url)
