"""Migración aditiva y compatibilidad congelada del traslado fiscal."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.core.evidencia_fiscal import COLUMNAS_EVIDENCIA, EVIDENCIA_HEAD
from app.core.fiscal_storage import compare_decimal
from app.core.fiscal_storage_legacy import A01_HEAD
from tests.test_alembic_migrations import (
    REVISION_INTEGRIDAD_FISCAL,
    _run_alembic,
    _run_alembic_failure,
    _backup_env_pf19,
    _crear_contexto_fiscal_sintetico,
    _insertar_intento_sintetico,
)


def crear_fuente_v6_con_evidencia(tmp_path):
    """Prepara un grafo íntegramente sintético con evidencia v1 transportable."""
    from types import SimpleNamespace
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.models.idempotencia_fiscal import IntentoEmisionFiscal
    from app.models.empresa import Empresa
    from app.models.comprobante import Comprobante
    from app.services.facturacion_service import FacturacionService
    from tests.integration.test_vps_migration_postgresql import _crear_fuente_v4_pf13

    source, certs = _crear_fuente_v4_pf13(tmp_path)
    _run_alembic("upgrade", EVIDENCIA_HEAD, f"sqlite:///{source.as_posix()}")
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    try:
        with Session(engine, expire_on_commit=False) as db:
            attempt = db.scalars(
                select(IntentoEmisionFiscal).where(
                    IntentoEmisionFiscal.grupo_id.is_not(None),
                    IntentoEmisionFiscal.guarda_rece_id.is_not(None),
                    IntentoEmisionFiscal.comprobante_id.is_not(None),
                )
            ).first()
            assert attempt is not None
            empresa = db.get(Empresa, attempt.empresa_id)
            service = FacturacionService(None)
            request = service._request_desde_comprobante_legacy(
                db.get(Comprobante, attempt.comprobante_id)
            )
            assert request is not None
            totales = service._calcular_totales(request.items)
            assert totales["total"] == attempt.total
            arca_request = service._armar_request_arca(
                request, attempt.numero_planificado, totales, attempt.punto_venta_numero
            )
            service._congelar_evidencia(
                attempt,
                request,
                arca_request,
                totales,
                empresa,
                SimpleNamespace(
                    cuit=empresa.cuit, config=SimpleNamespace(ambiente=attempt.ambiente)
                ),
            )
            db.commit()
            expected = (attempt.id, attempt.evidencia_json, attempt.evidencia_hash)
        return source, certs, expected
    finally:
        engine.dispose()


def test_v6_preserva_evidencia_completa_en_paquete(tmp_path):
    from app.scripts import vps_migration

    source, certs, expected = crear_fuente_v6_con_evidencia(tmp_path)
    package = vps_migration.export_package(
        source,
        certs,
        tmp_path / "packages",
        "clave-sintética-destino",
        source_key_password="clave-v3-sintetica",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    attempts = vps_migration.read_package_rows(
        package, manifest, "intentos_emision_fiscal"
    )
    actual = next(row for row in attempts if row["id"] == expected[0])
    assert (
        actual["id"],
        actual["evidencia_json"],
        actual["evidencia_hash"],
    ) == expected


def test_migracion_sqlite_conserva_antecedentes_y_rechaza_downgrade_con_evidencia(
    tmp_path,
):
    db_path = tmp_path / "sintetica.db"
    url = f"sqlite:///{db_path.as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, url)
    _crear_contexto_fiscal_sintetico(db_path)
    _insertar_intento_sintetico(db_path, row_id=1, estado="fallido_verificado")
    env = _backup_env_pf19(db_path, tmp_path / "backup.db")
    _run_alembic("upgrade", A01_HEAD, url, extra_env=env)

    def snapshot():
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            result = {}
            for (table,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
            ).fetchall():
                result[table] = [
                    {
                        key: value
                        for key, value in dict(row).items()
                        if key not in COLUMNAS_EVIDENCIA
                    }
                    for row in connection.execute(
                        f'SELECT * FROM "{table}" ORDER BY rowid'
                    )
                ]
            return result

    before = snapshot()
    _run_alembic("upgrade", EVIDENCIA_HEAD, url)
    assert snapshot() == before
    with sqlite3.connect(db_path) as connection:
        connection.create_collation("ff_decimal", compare_decimal)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute(
            "SELECT evidencia_version, evidencia_json, evidencia_hash FROM intentos_emision_fiscal"
        ).fetchone() == (None, None, None)
        for version, raw, checksum in (
            ("solicitud_fiscal/1", None, None),
            ("solicitud_fiscal/2", "{}", "a" * 64),
            ("solicitud_fiscal/1", "{}", "z" * 64),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE intentos_emision_fiscal SET evidencia_version=?, evidencia_json=?, evidencia_hash=?",
                    (version, raw, checksum),
                )
        connection.execute(
            "UPDATE intentos_emision_fiscal SET evidencia_version='solicitud_fiscal/1', evidencia_json='{}', evidencia_hash=?",
            (hashlib.sha256(b"{}").hexdigest(),),
        )
    before_failed_downgrade = db_path.read_bytes()
    assert "eliminaría evidencia fiscal" in _run_alembic_failure(
        "downgrade", A01_HEAD, url
    )
    assert db_path.read_bytes() == before_failed_downgrade
    # Sólo esta base sintética: ensayar la reversibilidad del esquema sin evidencia.
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE intentos_emision_fiscal SET evidencia_version=NULL, evidencia_json=NULL, evidencia_hash=NULL"
        )
    _run_alembic("downgrade", A01_HEAD, url)
    assert snapshot() == before
    _run_alembic("upgrade", EVIDENCIA_HEAD, url)
    assert snapshot() == before


def test_v6_exporta_sin_reescribir_contratos_v3_v4_v5(tmp_path):
    from app.scripts import (
        vps_migration,
        vps_migration_v3,
        vps_migration_v4,
        vps_migration_v5,
    )
    from tests.test_vps_migration import _create_source_db

    frozen = {
        module.__name__: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (vps_migration_v3, vps_migration_v4, vps_migration_v5)
    }
    source, certs = _create_source_db(tmp_path, fiscal_head=True)
    package = vps_migration.export_package(
        source,
        certs,
        tmp_path / "packages",
        "clave-sintética-destino",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    assert manifest["package_version"] == 6
    assert manifest["alembic_version"] == EVIDENCIA_HEAD
    for row in vps_migration.read_package_rows(
        package, manifest, "intentos_emision_fiscal"
    ):
        assert all(row[name] is None for name in COLUMNAS_EVIDENCIA)
    assert frozen == {
        module.__name__: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (vps_migration_v3, vps_migration_v4, vps_migration_v5)
    }


def test_paquete_v5_sigue_leyendo_su_esquema_congelado(tmp_path, monkeypatch):
    from app.scripts import vps_migration, vps_migration_v5
    from tests.test_vps_migration import _create_source_db

    source, certs = _create_source_db(tmp_path, fiscal_head=True)
    _run_alembic("downgrade", A01_HEAD, f"sqlite:///{source.as_posix()}")
    monkeypatch.setattr(vps_migration, "get_repo_alembic_head", lambda *_args: A01_HEAD)
    package = vps_migration.export_package(
        source,
        certs,
        tmp_path / "packages",
        "clave-sintética-destino",
        source_quiesced=True,
    )
    before = (package / "manifest.json").read_bytes()
    manifest = vps_migration.load_and_verify_manifest(package)
    assert manifest["package_version"] == 5
    assert manifest["alembic_version"] == A01_HEAD
    assert (
        vps_migration.select_import_contract(manifest) is vps_migration_v5.V4_CONTRACT
    )
    assert (package / "manifest.json").read_bytes() == before
    for row in vps_migration.read_package_rows(
        package, manifest, "intentos_emision_fiscal"
    ):
        assert not set(COLUMNAS_EVIDENCIA) & row.keys()
