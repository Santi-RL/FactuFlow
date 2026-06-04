"""Tests para la herramienta privada de migración a VPS."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, select, text

from app.arca.crypto import load_private_key
from app.core.database import Base
from app.scripts import vps_migration


def _write_private_key(path: Path) -> None:
    """Genera una clave privada temporal sin cifrar para tests."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _create_source_db(tmp_path: Path) -> tuple[Path, Path]:
    """Crea una SQLite fuente con datos sintéticos de operación futura."""
    db_path = tmp_path / "factuflow.db"
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    key_name = "20123456789_produccion_20260603_120000.key"
    cert_name = "20123456789_produccion_20260603_120000.crt"
    _write_private_key(certs_dir / key_name)
    (certs_dir / cert_name).write_bytes(b"certificado sintetico")

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": vps_migration.get_repo_alembic_head()},
        )
        conn.execute(
            Base.metadata.tables["empresas"].insert(),
            {
                "id": 10,
                "razon_social": "Empresa Sintetica S.A.",
                "cuit": "20123456789",
                "condicion_iva": "RI",
                "ingresos_brutos": "No informado",
                "domicilio": "Av. Test 123",
                "localidad": "Buenos Aires",
                "provincia": "Buenos Aires",
                "codigo_postal": "1000",
                "email": "test@example.com",
                "telefono": "123",
                "inicio_actividades": date(2020, 1, 1),
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["usuarios"].insert(),
            {
                "id": 20,
                "email": "admin@example.com",
                "hashed_password": "hash",
                "nombre": "Admin",
                "activo": True,
                "es_admin": True,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["clientes"].insert(),
            {
                "id": 30,
                "razon_social": "Cliente Sintetico",
                "tipo_documento": "CUIT",
                "numero_documento": "20999999991",
                "condicion_iva": "RI",
                "activo": True,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["puntos_venta"].insert(),
            {
                "id": 40,
                "numero": 6,
                "nombre": "Web Services",
                "es_webservice": True,
                "bloqueado": False,
                "activo": True,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["certificados"].insert(),
            {
                "id": 50,
                "nombre": "Certificado productivo",
                "cuit": "20123456789",
                "fecha_emision": date(2026, 6, 3),
                "fecha_vencimiento": date(2028, 6, 3),
                "archivo_crt": cert_name,
                "archivo_key": key_name,
                "activo": True,
                "ambiente": "produccion",
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["formatos_importacion"].insert(),
            {
                "id": 60,
                "nombre": "Formato sintetico",
                "descripcion": "Formato de test",
                "alcance": "emisor",
                "activo": True,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["formatos_importacion_versiones"].insert(),
            {
                "id": 70,
                "version": 1,
                "estado": "vigente",
                "configuracion_json": {"tipo": "test"},
                "headers_firma_json": ["Fecha", "Total"],
                "formato_id": 60,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["formatos_importacion_campos"].insert(),
            {
                "id": 80,
                "campo_destino": "fecha_emision",
                "origen_tipo": "encabezado",
                "encabezado": "Fecha",
                "requerido": True,
                "version_id": 70,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["formatos_importacion_reglas"].insert(),
            {
                "id": 90,
                "nombre": "Regla sintetica",
                "tipo": "constante",
                "configuracion_json": {"valor": "x"},
                "orden": 1,
                "activo": True,
                "version_id": 70,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["perfiles_carga_masiva"].insert(),
            {
                "id": 100,
                "nombre": "Perfil sintetico",
                "descripcion": "Perfil de test",
                "configuracion_json": {"formato_importacion_version_id": 70},
                "es_predeterminado": True,
                "activo": True,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["comprobantes"].insert(),
            {
                "id": 110,
                "tipo_comprobante": 6,
                "concepto": 1,
                "numero": 123,
                "fecha_emision": date(2026, 6, 3),
                "subtotal": Decimal("100.00"),
                "descuento": Decimal("0.00"),
                "iva_21": Decimal("21.00"),
                "iva_10_5": Decimal("0.00"),
                "iva_27": Decimal("0.00"),
                "otros_impuestos": Decimal("0.00"),
                "total": Decimal("121.00"),
                "cae": "12345678901234",
                "cae_vencimiento": date(2026, 6, 13),
                "estado": "autorizado",
                "origen_emision": "factuflow",
                "moneda": "PES",
                "cotizacion": Decimal("1.000000"),
                "empresa_id": 10,
                "punto_venta_id": 40,
                "cliente_id": 30,
                "receptor_tipo_documento": 80,
                "receptor_numero_documento": "20999999991",
                "receptor_razon_social": "Cliente Sintetico",
                "receptor_condicion_iva": "RI",
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["comprobante_items"].insert(),
            {
                "id": 120,
                "descripcion": "Item sintetico",
                "cantidad": Decimal("1.0000"),
                "unidad": "unidades",
                "precio_unitario": Decimal("100.0000"),
                "descuento_porcentaje": Decimal("0.00"),
                "iva_porcentaje": Decimal("21.00"),
                "subtotal": Decimal("100.00"),
                "orden": 1,
                "comprobante_id": 110,
            },
        )
        conn.execute(
            Base.metadata.tables["lotes_comprobantes"].insert(),
            {
                "id": 130,
                "nombre_archivo": "privado.xlsx",
                "archivo_hash": "a" * 64,
                "estado": "completado",
                "modo_procesamiento": "sincronico",
                "procesamiento_async": False,
                "total_filas": 1,
                "total_grupos": 1,
                "grupos_validos": 1,
                "grupos_con_error": 0,
                "grupos_emitidos": 1,
                "grupos_fallidos": 0,
                "grupos_reconciliados_externos": 0,
                "grupos_descartados": 0,
                "empresa_id": 10,
                "usuario_id": 20,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )

    return db_path, certs_dir


def test_exporta_solo_tablas_incluidas_y_excluye_lotes(tmp_path: Path) -> None:
    """El paquete debe omitir lotes y artefactos, pero conservar comprobantes."""
    db_path, certs_dir = _create_source_db(tmp_path)

    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
    )

    manifest = vps_migration.load_and_verify_manifest(package)
    assert set(manifest["included_tables"]) == set(vps_migration.INCLUDED_TABLES)
    assert "lotes_comprobantes" not in manifest["data_files"]
    assert not (package / "data" / "lotes_comprobantes.jsonl").exists()
    assert manifest["data_files"]["comprobantes"]["rows"] == 1
    assert manifest["excluded_counts"]["lotes_comprobantes"] == 1


def test_preflight_falla_si_certificado_activo_no_tiene_archivos(
    tmp_path: Path,
) -> None:
    """La exportación debe bloquear certificados activos incompletos."""
    db_path, certs_dir = _create_source_db(tmp_path)
    for path in certs_dir.iterdir():
        path.unlink()

    with pytest.raises(vps_migration.MigrationError) as exc:
        vps_migration.run_preflight(db_path, certs_dir)

    assert "certificados activos" in str(exc.value)
    assert "IDs afectados: 50" in str(exc.value)


def test_recifra_clave_privada_con_password_destino(tmp_path: Path) -> None:
    """Una clave exportada debe abrir solo con la contraseña destino."""
    source_key = tmp_path / "origen.key"
    target_key = tmp_path / "destino.key"
    _write_private_key(source_key)

    vps_migration.reencrypt_private_key(
        source_key=source_key,
        target_key=target_key,
        target_password="clave-destino-larga",
    )

    assert b"ENCRYPTED PRIVATE KEY" in target_key.read_bytes()
    assert load_private_key(str(target_key), password=b"clave-destino-larga")


def test_verifica_password_destino_del_paquete(tmp_path: Path) -> None:
    """El paquete debe rechazar una ARCA_PRIVATE_KEY_PASSWORD incorrecta."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
    )
    manifest = vps_migration.load_and_verify_manifest(package)

    vps_migration.verify_package_certificates(package, manifest, "clave-destino-larga")
    with pytest.raises(vps_migration.MigrationError):
        vps_migration.verify_package_certificates(package, manifest, "otra-clave")


def test_rechaza_nombres_de_certificados_con_path_traversal(tmp_path: Path) -> None:
    """El importador no debe aceptar destinos de certificados fuera de CERTS_PATH."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filename, info = next(iter(manifest["certificate_files"].items()))
    manifest["certificate_files"] = {f"../{filename}": info}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="Nombre de certificado"):
        vps_migration.load_and_verify_manifest(package)


def test_inserta_filas_preservando_ids_y_relaciones(tmp_path: Path) -> None:
    """La carga de filas del paquete debe preservar IDs y relaciones."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        for table_name in vps_migration.INCLUDED_TABLES:
            rows = vps_migration.read_package_rows(package, manifest, table_name)
            vps_migration.insert_rows(conn, table_name, rows)

        comprobante = conn.execute(
            select(Base.metadata.tables["comprobantes"]).where(
                Base.metadata.tables["comprobantes"].c.id == 110
            )
        ).first()
        item_count = conn.execute(
            select(Base.metadata.tables["comprobante_items"].c.comprobante_id)
        ).scalar_one()

    assert comprobante is not None
    assert item_count == 110


class _ScalarResult:
    """Resultado mínimo compatible con `scalar()` para tests de secuencias."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar(self) -> Any:
        return self.value


class _FakeSequenceConnection:
    """Conexión fake para verificar llamadas PostgreSQL de secuencias."""

    def __init__(self, max_ids: dict[str, int | None]) -> None:
        self.max_ids = max_ids
        self.current_table: str | None = None
        self.setvals: dict[str, tuple[int, bool]] = {}

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> Any:
        assert params is not None or "setval" not in str(statement)
        sql = str(statement)
        if "pg_get_serial_sequence" in sql:
            assert params is not None
            self.current_table = params["table_name"]
            return _ScalarResult(f"{self.current_table}_id_seq")
        if "setval" in sql:
            assert params is not None
            value = params.get("value", 1)
            self.setvals[params["seq"]] = (value, "true)" in sql)
            return _ScalarResult(None)
        assert self.current_table is not None
        return _ScalarResult(self.max_ids.get(self.current_table))


def test_ajusta_secuencias_al_maximo_id_restaurado() -> None:
    """Las secuencias deben quedar alineadas al mayor ID de cada tabla."""
    max_ids = {table_name: None for table_name in vps_migration.INCLUDED_TABLES}
    max_ids["empresas"] = 10
    max_ids["comprobantes"] = 110
    conn = _FakeSequenceConnection(max_ids)

    vps_migration.reset_postgres_sequences(conn)

    assert conn.setvals["empresas_id_seq"] == (10, True)
    assert conn.setvals["comprobantes_id_seq"] == (110, True)
    assert conn.setvals["usuarios_id_seq"] == (1, False)


class _ContextManager:
    """Context manager mínimo para simular conexiones SQLAlchemy."""

    def __init__(self, conn: object) -> None:
        self.conn = conn

    def __enter__(self) -> object:
        return self.conn

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _FakeEngine:
    """Engine fake para verificar orden de importación."""

    def __init__(self) -> None:
        self.conn = object()

    def connect(self) -> _ContextManager:
        return _ContextManager(self.conn)

    def begin(self) -> _ContextManager:
        return _ContextManager(self.conn)


def _write_production_env(path: Path) -> None:
    """Escribe un `.env.production` sintético para tests de importación."""
    path.write_text(
        "\n".join(
            [
                "APP_SECRET_KEY=clave",
                "ARCA_PRIVATE_KEY_PASSWORD=clave-destino-larga",
                "POSTGRES_DB=factuflow",
                "POSTGRES_USER=factuflow",
                "POSTGRES_PASSWORD=password",
                "ARCA_ENV=produccion",
                "CORS_ORIGINS=http://localhost:8080",
                "VITE_API_URL=http://localhost:8000",
                f"FACTUFLOW_CERTS_DIR={path.parent / 'target-certs'}",
            ]
        ),
        encoding="utf-8",
    )


def test_import_no_inserta_filas_si_falla_restauracion_de_certificados(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un fallo copiando certificados no debe dejar la base parcialmente cargada."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    events: list[str] = []

    def fail_restore(*args, **kwargs) -> None:
        events.append("restore")
        raise vps_migration.MigrationError("sin permisos")

    monkeypatch.setattr(
        vps_migration,
        "create_postgres_engine",
        lambda database_url: _FakeEngine(),
    )
    monkeypatch.setattr(
        vps_migration,
        "ensure_target_database_ready",
        lambda conn, manifest: events.append("ready"),
    )
    monkeypatch.setattr(vps_migration, "restore_certificate_files", fail_restore)
    monkeypatch.setattr(
        vps_migration,
        "clear_seeded_included_tables",
        lambda conn: events.append("clear"),
    )
    monkeypatch.setattr(
        vps_migration,
        "insert_rows",
        lambda conn, table_name, rows: events.append(f"insert:{table_name}"),
    )
    monkeypatch.setattr(
        vps_migration,
        "reset_postgres_sequences",
        lambda conn: events.append("seq"),
    )

    with pytest.raises(vps_migration.MigrationError, match="sin permisos"):
        vps_migration.import_package(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
        )

    assert events == ["ready", "restore"]
