"""Tests para la herramienta privada de migración a VPS."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import create_engine, select, text

from app.arca.crypto import load_private_key
from app.core.database import Base
from app.schemas.lote_comprobante import LoteComprobanteResponse
from app.scripts import vps_migration, vps_migration_v3, vps_migration_v4

_CERT_TEST_NOW = datetime.now().replace(microsecond=0)
_CERT_TEST_NOT_BEFORE = _CERT_TEST_NOW - timedelta(days=30)
_CERT_TEST_NOT_AFTER = _CERT_TEST_NOW + timedelta(days=3650)


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


def _write_certificate_pair(
    cert_path: Path,
    key_path: Path,
    *,
    cuit: str,
    not_before: datetime | None = None,
    not_after: datetime | None = None,
) -> None:
    """Genera un par X.509 sintético autocontenido sin datos reales."""
    valid_from = not_before or _CERT_TEST_NOT_BEFORE
    valid_until = not_after or _CERT_TEST_NOT_AFTER
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"CUIT {cuit}")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(valid_until)
        .sign(private_key, hashes.SHA256())
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
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
    _write_certificate_pair(
        certs_dir / cert_name,
        certs_dir / key_name,
        cuit="20123456789",
    )

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
            Base.metadata.tables["lotes_duplicados_coordinacion"].insert(),
            [
                {
                    "empresa_id": 10,
                    "ambiente": "homologacion",
                    "revision": 0,
                },
                {
                    "empresa_id": 10,
                    "ambiente": "produccion",
                    "revision": 0,
                },
            ],
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
                "puede_crear_editar_emisores": False,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        conn.execute(
            Base.metadata.tables["usuario_emisor_acceso"].insert(),
            {
                "usuario_id": 20,
                "empresa_id": 10,
                "otorgado_por_usuario_id": None,
                "origen": "migracion_legacy",
                "otorgado_en": datetime(2026, 6, 3, 12, 0, 0),
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
                "revision_fiscal": 1,
                "empresa_id": 10,
                "created_at": datetime(2026, 6, 3, 12, 0, 0),
            },
        )
        for revision_id, ambiente in ((41, "homologacion"), (42, "produccion")):
            conn.execute(
                Base.metadata.tables[
                    "puntos_venta_elegibilidad_rece_revisiones"
                ].insert(),
                {
                    "id": revision_id,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": ambiente,
                    "revision": 1,
                    "estado": "no_verificado",
                    "fuente": "migracion_legacy",
                    "evidencia_tipo": "sin_evidencia",
                    "punto_revision_fiscal": 1,
                    "observado_en": datetime(2026, 6, 3, 12, 0, 0),
                    "creado_por_usuario_id": 20,
                    "actor_usuario_id_snapshot": 20,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
        for head_id, ambiente, revision_id in (
            (43, "homologacion", 41),
            (44, "produccion", 42),
        ):
            conn.execute(
                Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"].insert(),
                {
                    "id": head_id,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": ambiente,
                    "revision_actual_id": revision_id,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
        conn.execute(
            Base.metadata.tables["certificados"].insert(),
            {
                "id": 50,
                "nombre": "Certificado productivo",
                "cuit": "20123456789",
                "fecha_emision": _CERT_TEST_NOT_BEFORE.date(),
                "fecha_vencimiento": _CERT_TEST_NOT_AFTER.date(),
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


def _lote_response_payload() -> dict[str, Any]:
    """Devuelve el DTO completo y coherente del lote sintético fuente."""
    return {
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
        "mensaje_resumen": None,
        "metadata_json": None,
        "mapeo_usado_json": None,
        "headers_detectados_json": None,
        "started_at": None,
        "finished_at": None,
        "compactado_at": None,
        "created_at": "2026-06-03T12:00:00",
        "updated_at": "2026-06-03T12:00:00",
        "empresa_id": 10,
        "usuario_id": 20,
        "formato_importacion_id": None,
        "formato_importacion_version_id": None,
    }


def _insert_operation(
    db_path: Path,
    *,
    estado: str,
    response_json: dict[str, Any] | None,
    tipo_operacion: str = "procesar_lote",
    lote_id: int | None = 130,
    operacion_id: int = 140,
    empresa_id: int = 10,
) -> None:
    """Inserta una operación idempotente sintética con identidad estable."""
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"].insert(),
                {
                    "id": operacion_id,
                    "idempotency_key": f"vps-operacion-{operacion_id}",
                    "tipo_operacion": tipo_operacion,
                    "payload_hash": "b" * 64,
                    "estado": estado,
                    "response_json": response_json,
                    "lote_id": lote_id,
                    "empresa_id": empresa_id,
                    "usuario_id": 20,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
    finally:
        engine.dispose()


def _v4_lote_row(lote_id: int, *, total_grupos: int, estado: str) -> dict[str, Any]:
    timestamp = "2026-09-05 12:00:00"
    return {
        "id": lote_id,
        "nombre_archivo": f"lote-{lote_id}.xlsx",
        "archivo_hash": hashlib.sha256(str(lote_id).encode("ascii")).hexdigest(),
        "estado": estado,
        "modo_procesamiento": "sincronico",
        "procesamiento_async": 0,
        "total_filas": total_grupos,
        "total_grupos": total_grupos,
        "grupos_validos": total_grupos,
        "grupos_con_error": 0,
        "grupos_emitidos": 1,
        "grupos_fallidos": max(0, total_grupos - 1),
        "grupos_reconciliados_externos": 0,
        "grupos_descartados": 0,
        "mensaje_resumen": None,
        "metadata_json": None,
        "mapeo_usado_json": None,
        "headers_detectados_json": None,
        "started_at": timestamp,
        "finished_at": timestamp,
        "compactado_at": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "empresa_id": 10,
        "usuario_id": 20,
        "formato_importacion_id": 60,
        "formato_importacion_version_id": 61,
    }


def _v4_group_row(
    group_id: int,
    lote_id: int,
    *,
    estado: str,
    receipt_id: int | None,
    reserved_by: int | None = None,
    numero_asignado: int | None = None,
) -> dict[str, Any]:
    timestamp = "2026-09-05 12:00:00"
    return {
        "id": group_id,
        "comprobante_ref": f"grupo-{group_id}",
        "orden": group_id,
        "estado": estado,
        "tipo_comprobante": 6,
        "punto_venta_numero": 6,
        "cliente_documento": "20999999991",
        "cliente_razon_social": "Cliente Sintético",
        "total_estimado": "121.00",
        "payload_json": json.dumps({"grupo_id": group_id}, sort_keys=True),
        "duplicados_version": "duplicados_lotes/v2",
        "duplicados_cobertura": "completa",
        "huella_fiscal_completa": f"{group_id % 10}" * 64,
        "identidad_nombre_hash": "a" * 64,
        "identidad_documento_hash": "b" * 64,
        "identidad_nombre_original": "Cliente Sintético",
        "identidad_tipo_documento_original": 80,
        "identidad_numero_documento_original": "20999999991",
        "fecha_emision_normalizada": "2026-09-05",
        "moneda_duplicados": "PES",
        "cotizacion_duplicados": "1.000000",
        "total_centavos": 12100,
        "duplicados_reserva_operacion_id": reserved_by,
        "mensajes_json": json.dumps([], sort_keys=True),
        "cae": "12345678901234" if receipt_id is not None else None,
        "numero_asignado": numero_asignado if receipt_id is not None else None,
        "empresa_id": 10,
        "punto_venta_id": 40,
        "ambiente": "produccion",
        "punto_venta_elegibilidad_revision_id": 42,
        "punto_venta_revision_fiscal": 1,
        "comprobante_id": receipt_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "lote_id": lote_id,
    }


def _v4_lote_replay_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    for field_name in ("metadata_json", "mapeo_usado_json", "headers_detectados_json"):
        if isinstance(payload[field_name], str):
            payload[field_name] = json.loads(payload[field_name])
    return LoteComprobanteResponse.model_validate(payload).model_dump(mode="json")


def _v4_legacy_preflight() -> dict[str, Any]:
    excluded_counts = {table_name: 0 for table_name in vps_migration_v3.EXCLUDED_TABLES}
    excluded_counts.update(
        {
            "intentos_emision_fiscal": 2,
            "puntos_venta_guardas_emision_rece": 1,
            "lotes_comprobantes": 3,
            "lotes_comprobantes_grupos": 101,
        }
    )
    return {
        "blockers": 0,
        "excluded_counts": excluded_counts,
        "operaciones_terminales_preservadas": 5,
        "operaciones_lote_normalizado": 4,
        "asociaciones_rece_preservadas": 2,
        "intentos_terminales_omitidos": 2,
        "resoluciones_legacy_pf19_omitidas": 0,
        "guardas_terminales_omitidas": 1,
        "lotes_seguros_omitidos": 3,
        "grupos_seguros_omitidos": 101,
        "filas_omitidas": 0,
        "eventos_lote_omitidos": 0,
        "eventos_sistema_omitidos": 0,
        "exportaciones_omitidas": 0,
    }


def _v4_fixture_rows(tmp_path: Path) -> tuple[Path, dict[str, list[dict[str, Any]]]]:
    package = _build_historical_v3_package(tmp_path)
    rows = {
        table_name: [
            json.loads(line)
            for line in (package / "data" / f"{table_name}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        for table_name in vps_migration_v4.COMPLETE_TABLES
    }
    base_receipt = rows["comprobantes"][0]
    base_receipt.update(
        {"fecha_emision": "2026-09-05", "cae_vencimiento": "2026-09-15"}
    )
    base_item = rows["comprobante_items"][0]
    for offset in range(15):
        receipt_id = 111 + offset
        rows["comprobantes"].append(
            {
                **base_receipt,
                "id": receipt_id,
                "numero": 124 + offset,
            }
        )
        rows["comprobante_items"].append(
            {
                **base_item,
                "id": 121 + offset,
                "comprobante_id": receipt_id,
            }
        )

    legacy_operation = rows["operaciones_idempotentes"][0]
    legacy_operation.update(
        {
            "control_duplicados_json": None,
            "duplicados_version": None,
            "duplicados_generacion_id": None,
            "operacion_raiz_id": None,
            "solicitante_nombre_snapshot": None,
            "solicitud_emision_at": None,
        }
    )
    rows["lotes_comprobantes"] = [
        _v4_lote_row(90, total_grupos=1, estado="completado"),
        {
            **_v4_lote_row(100, total_grupos=100, estado="completado"),
            "grupos_validos": 85,
            "grupos_con_error": 15,
            "grupos_emitidos": 10,
            "grupos_fallidos": 25,
            "grupos_reconciliados_externos": 5,
            "grupos_descartados": 20,
        },
    ]
    rows["lotes_comprobantes_grupos"] = [
        _v4_group_row(
            91,
            90,
            estado="autorizado",
            receipt_id=110,
            numero_asignado=123,
        )
    ]
    state_ranges = (
        (range(101, 111), "autorizado"),
        (range(111, 116), "autorizado_externo"),
        (range(116, 126), "cargado"),
        (range(126, 141), "validado"),
        (range(141, 156), "con_error"),
        (range(156, 181), "fallido"),
        (range(181, 201), "descartado"),
    )
    for group_ids, state in state_ranges:
        for group_id in group_ids:
            is_authorized = state in {"autorizado", "autorizado_externo"}
            rows["lotes_comprobantes_grupos"].append(
                _v4_group_row(
                    group_id,
                    100,
                    estado=state,
                    receipt_id=group_id + 10 if is_authorized else None,
                    reserved_by=200 if group_id == 101 else None,
                    numero_asignado=group_id + 23 if is_authorized else None,
                )
            )

    lote_90_response = _v4_lote_replay_payload(rows["lotes_comprobantes"][0])
    lote_100_response = _v4_lote_replay_payload(rows["lotes_comprobantes"][1])
    selection = [{"grupo_id": 101}]
    generation_control = {
        "formato_relacion": vps_migration_v4.RELATION_FORMAT,
        "evidencia_id": "evidencia-compartida",
        "datos_hash": "d" * 64,
        "seleccion_hash": "e" * 64,
        "seleccion_original": selection,
        "manifiesto": {"bloques": 1, "miembros": 2},
    }
    association = {
        "id": 142,
        "operacion_id": 200,
        "empresa_id": 10,
        "punto_venta_id": 40,
        "ambiente": "produccion",
        "elegibilidad_revision_id": 42,
        "punto_venta_revision_fiscal": 1,
        "created_at": "2026-09-05 12:00:00",
    }
    rece_digest = vps_migration._digest_asociaciones_rece(
        [{**association, "punto_venta_numero": 6}]
    )
    operation_specs = (
        (200, "procesar_lote", 301, 2, 200),
        (201, "reintentar_fallidos_lote", 302, 1, 200),
    )
    for (
        operation_id,
        operation_type,
        generation_id,
        generation_number,
        root_id,
    ) in operation_specs:
        control = {
            **generation_control,
            "duplicados_generacion_id": generation_id,
            "duplicados_generacion": generation_number,
        }
        response = {
            "lote": lote_100_response,
            "mensaje": "Lote procesado",
            "errores_arca": [],
        }
        if operation_type == "procesar_lote":
            response["en_progreso"] = False
        rows["operaciones_idempotentes"].append(
            {
                **legacy_operation,
                "id": operation_id,
                "idempotency_key": f"v4-operacion-{operation_id}",
                "tipo_operacion": operation_type,
                "payload_hash": f"{operation_id % 10}" * 64,
                "response_json": json.dumps(response, sort_keys=True),
                "control_duplicados_json": json.dumps(control, sort_keys=True),
                "duplicados_version": "duplicados_lotes/v2",
                "duplicados_generacion_id": generation_id,
                "operacion_raiz_id": root_id,
                "solicitante_nombre_snapshot": "Operador Sintético",
                "solicitud_emision_at": "2026-09-05 12:00:00+00:00",
                "rece_snapshot_hash": rece_digest if operation_id == 200 else None,
                "lote_id": 100,
            }
        )
    rows["operaciones_idempotentes"].append(
        {
            **legacy_operation,
            "id": 202,
            "idempotency_key": "legacy-preservada-202",
            "payload_hash": "2" * 64,
            "response_json": json.dumps(
                {
                    "lote": lote_90_response,
                    "mensaje": "Lote procesado",
                    "en_progreso": False,
                },
                sort_keys=True,
            ),
            "rece_snapshot_hash": None,
            "lote_id": 90,
        }
    )
    rows["operaciones_idempotentes"].append(
        {
            **legacy_operation,
            "id": 203,
            "idempotency_key": "individual-legacy-203",
            "tipo_operacion": "emitir_comprobante",
            "payload_hash": "3" * 64,
            "response_json": json.dumps(
                {
                    "exito": True,
                    "comprobante_id": 110,
                    "tipo_comprobante": 6,
                    "punto_venta": 6,
                    "numero": 123,
                    "fecha": "2026-09-05",
                    "cae": "12345678901234",
                    "cae_vencimiento": "2026-09-15",
                    "total": "121.00",
                    "mensaje": "Autorizado",
                    "errores": [],
                    "errores_arca": [],
                    "requiere_reconciliacion": False,
                },
                sort_keys=True,
            ),
            "rece_snapshot_hash": None,
            "lote_id": None,
        }
    )
    rows["operaciones_idempotentes_elegibilidad_rece"].append(association)
    rows["puntos_venta_guardas_emision_rece"] = [
        {
            "id": 600,
            "token": "f" * 64,
            "fase": "cerrada_terminal",
            "operacion_id": 200,
            "empresa_id": 10,
            "punto_venta_id": 40,
            "ambiente": "produccion",
            "elegibilidad_revision_id": 42,
            "punto_venta_revision_fiscal": 1,
            "arca_iniciada_en": "2026-09-05 12:00:00",
            "cerrada_en": "2026-09-05 12:01:00",
            "created_at": "2026-09-05 12:00:00",
            "updated_at": "2026-09-05 12:01:00",
        }
    ]
    block_rows = []
    member_rows = []
    for generation_id, operation_id, block_id, member_base in (
        (300, 200, 400, 500),
        (301, 200, 401, 502),
        (302, 201, 402, 504),
    ):
        block_rows.append(
            {
                "id": block_id,
                "generacion_id": generation_id,
                "operacion_id": operation_id,
                "empresa_id": 10,
                "ambiente": "produccion",
                "lote_id": 100,
                "bloque_clave": "bloque-completo",
                "clase": "completa",
                "antecedente_clave": "huella-previa",
                "snapshot_json": json.dumps({"multiplicidad_total": 1}, sort_keys=True),
            }
        )
        member_rows.extend(
            [
                {
                    "id": member_base,
                    "bloque_id": block_id,
                    "lado": "actual",
                    "miembro_clave": "actual-101",
                    "grupo_id": 101,
                    "comprobante_id": None,
                    "nombre_hash": "a" * 64,
                    "documento_hash": "b" * 64,
                    "ordinal": 0,
                    "relevancia": "actual",
                    "snapshot_json": json.dumps(
                        {"decision": {"grupo_id": 101}}, sort_keys=True
                    ),
                },
                {
                    "id": member_base + 1,
                    "bloque_id": block_id,
                    "lado": "anterior",
                    "miembro_clave": "anterior-110",
                    "grupo_id": None,
                    "comprobante_id": 110,
                    "nombre_hash": "a" * 64,
                    "documento_hash": "b" * 64,
                    "ordinal": 0,
                    "relevancia": "autorizado",
                    "snapshot_json": json.dumps(
                        {"decision": {"comprobante_id": 110}}, sort_keys=True
                    ),
                },
            ]
        )
    rows["lotes_duplicados_coincidencias"] = block_rows
    rows["lotes_duplicados_coincidencias_miembros"] = member_rows
    rows["lotes_duplicados_evidencias"] = []
    for generation_id, operation_id, generation_number, origin_id in (
        (300, 200, 1, 300),
        (301, 200, 2, 300),
        (302, 201, 1, 300),
    ):
        generation = {
            "id": generation_id,
            "operacion_id": operation_id,
            "empresa_id": 10,
            "ambiente": "produccion",
            "lote_id": 100,
            "generacion": generation_number,
            "formato": vps_migration_v4.RELATION_FORMAT,
            "evidencia_id": "evidencia-compartida",
            "snapshot_hash": "0" * 64,
            "control_snapshot_json": json.dumps(generation_control, sort_keys=True),
            "aceptacion_id": "aceptacion-compartida",
            "aceptada_por_usuario_id": 20,
            "aceptada_por_nombre": "Operador Sintético",
            "aceptada_at": "2026-09-05 12:02:00+00:00",
            "aceptacion_origen_generacion_id": origin_id,
            "created_at": "2026-09-05 12:00:00+00:00",
        }
        relation = vps_migration._v4_generation_relation(
            generation,
            blocks=[row for row in block_rows if row["generacion_id"] == generation_id],
            members_by_block={
                block_id: [row for row in member_rows if row["bloque_id"] == block_id]
                for block_id in (400, 401, 402)
            },
            group_ids={row["id"] for row in rows["lotes_comprobantes_grupos"]},
            receipt_ids={row["id"] for row in rows["comprobantes"]},
        )
        generation["snapshot_hash"] = vps_migration_v4.canonical_sha256(
            {
                "dominio": vps_migration_v4.RELATION_FORMAT,
                "control": generation_control,
                "relacion": relation,
            }
        )
        rows["lotes_duplicados_evidencias"].append(generation)
    rows["intentos_emision_fiscal"] = [
        {
            "id": 700,
            "tipo_comprobante": 6,
            "punto_venta_numero": 6,
            "numero_planificado": 124,
            "fecha_emision": "2026-09-05",
            "total": "121.00",
            "receptor_tipo_documento": 80,
            "receptor_numero_documento": "20999999991",
            "receptor_razon_social": "Cliente Sintético",
            "payload_hash": "7" * 64,
            "huella_logica": "8" * 64,
            "cae": "12345678901234",
            "cae_vencimiento": "2026-09-15",
            "estado": "autorizado",
            "categoria_error": None,
            "mensaje": "Autorizado",
            "errores_arca_json": None,
            "solicitante_nombre_snapshot": "Operador Sintético",
            "solicitud_arca_at": "2026-09-05 12:00:00+00:00",
            "resultado_fiscal_at": "2026-09-05 12:01:00+00:00",
            "ambiente": "produccion",
            "punto_venta_elegibilidad_revision_id": 42,
            "punto_venta_revision_fiscal": 1,
            "guarda_rece_id": 600,
            "created_at": "2026-09-05 12:00:00",
            "updated_at": "2026-09-05 12:01:00",
            "operacion_id": 200,
            "empresa_id": 10,
            "usuario_id": 20,
            "punto_venta_id": 40,
            "comprobante_id": 111,
            "lote_id": 100,
            "grupo_id": 101,
            "duplicados_generacion_id": 300,
        }
    ]
    rows["intentos_emision_fiscal"].append(
        {
            **rows["intentos_emision_fiscal"][0],
            "id": 701,
            "numero_planificado": 123,
            "payload_hash": "9" * 64,
            "huella_logica": "a" * 64,
            "ambiente": None,
            "punto_venta_elegibilidad_revision_id": None,
            "punto_venta_revision_fiscal": None,
            "guarda_rece_id": None,
            "operacion_id": 202,
            "comprobante_id": 110,
            "lote_id": 90,
            "grupo_id": 91,
            "duplicados_generacion_id": None,
        }
    )
    for table_name in rows:
        primary_key = vps_migration_v4.PRIMARY_KEYS[table_name]
        rows[table_name].sort(key=lambda row: tuple(row[name] for name in primary_key))
    return package, rows


def _write_v4_package(
    package: Path,
    rows: dict[str, list[dict[str, Any]]],
    *,
    previous_manifest: dict[str, Any],
) -> dict[str, Any]:
    data_files = {}
    for table_name in vps_migration_v4.INCLUDED_TABLES:
        path = package / "data" / f"{table_name}.jsonl"
        raw = b"".join(
            (
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
            ).encode("utf-8")
            for row in rows[table_name]
        )
        path.write_bytes(raw)
        data_files[table_name] = {
            "path": f"data/{table_name}.jsonl",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows[table_name]),
            "bytes": len(raw),
        }
    normalization_pairs = [
        {
            "operacion_id": 140,
            "lote_id": 130,
            "grupo_ids": [],
            "grupos_rechazo_ids": [],
            "grupos_no_enviados_ids": [],
        }
    ]
    normalization = {
        "rule": vps_migration_v4.OPERATION_LOTE_NORMALIZATION_RULE,
        "rows": 1,
        "sha256": vps_migration_v4.canonical_sha256(normalization_pairs),
        "pairs": normalization_pairs,
    }
    closure = vps_migration._v4_closure_payload(
        rows=rows,
        normalization=normalization,
    )
    included_counts = {table_name: len(rows[table_name]) for table_name in rows}
    omitted_counts = {
        table_name: 1 if table_name == "lotes_comprobantes" else 0
        for table_name in (
            vps_migration_v4.FILTERED_TABLES + vps_migration_v4.EXCLUDED_TABLES
        )
    }
    source_counts = {
        table_name: included_counts.get(table_name, 0)
        + omitted_counts.get(table_name, 0)
        for table_name in (
            vps_migration_v4.INCLUDED_TABLES
            + vps_migration_v4.REGENERATED_TABLES
            + vps_migration_v4.EXCLUDED_TABLES
        )
    }
    source_counts["lotes_duplicados_coordinacion"] = 2
    source_barrier = {
        "source_quiesced": True,
        "sqlite_transaction": "BEGIN IMMEDIATE",
        "data_version": 0,
    }
    safe_omitted = {
        "blockers": 0,
        "legacy_preflight": _v4_legacy_preflight(),
        "source_counts": source_counts,
        "included_counts": included_counts,
        "omitted_counts": omitted_counts,
    }
    manifest = {
        "package_version": 4,
        "created_at": "2026-09-05T12:00:00+00:00",
        "scope": vps_migration_v4.SCOPE,
        "alembic_version": vps_migration_v4.ALEMBIC_HEAD,
        "complete_tables": list(vps_migration_v4.COMPLETE_TABLES),
        "filtered_tables": list(vps_migration_v4.FILTERED_TABLES),
        "regenerated_tables": list(vps_migration_v4.REGENERATED_TABLES),
        "included_tables": list(vps_migration_v4.INCLUDED_TABLES),
        "excluded_tables": list(vps_migration_v4.EXCLUDED_TABLES),
        "target_empty_tables": list(vps_migration_v4.TARGET_EMPTY_TABLES),
        "source_counts": source_counts,
        "included_counts": included_counts,
        "omitted_counts": omitted_counts,
        "active_certificates": 1,
        "safe_omitted": safe_omitted,
        "normalizations": {
            vps_migration_v4.OPERATION_LOTE_NORMALIZATION_KEY: normalization
        },
        "closure": closure,
        "source_barrier": source_barrier,
        "idempotency_barrier": vps_migration.build_v4_idempotency_barrier(
            source_barrier=source_barrier,
            normalization=normalization,
            closure=closure,
            rows=rows,
        ),
        "data_files": data_files,
        "certificate_files": previous_manifest["certificate_files"],
        "env_template": previous_manifest["env_template"],
        "required_env_keys": list(vps_migration_v3.REQUIRED_ENV_KEYS),
        "notes": list(vps_migration_v4.PACKAGE_NOTES),
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _build_v4_package(
    tmp_path: Path,
) -> tuple[Path, dict[str, list[dict[str, Any]]], dict[str, Any]]:
    package, rows = _v4_fixture_rows(tmp_path)
    previous_manifest = json.loads(
        (package / "manifest.json").read_text(encoding="utf-8")
    )
    manifest = _write_v4_package(
        package,
        rows,
        previous_manifest=previous_manifest,
    )
    return package, rows, manifest


def _apply_v4_pf19c_rejection_with_successor(
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    lote = _v4_lote_replay_payload(rows["lotes_comprobantes"][1])
    errors = [dict(item) for item in vps_migration.ARCA_RECHAZO_GLOBAL_ERRORES]
    lote["metadata_json"] = {
        "pf19c_rechazo_global": {
            "operacion_id": 200,
            "categoria": vps_migration.ARCA_RECHAZO_GLOBAL_CATEGORIA,
            "grupos_rechazo_ids": [101],
            "grupos_no_enviados_ids": [],
            "errores_arca": errors,
        }
    }
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    operation.update(
        {
            "estado": "rechazado_arca",
            "response_json": json.dumps(
                {
                    "lote": lote,
                    "mensaje": vps_migration.ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE,
                    "en_progreso": False,
                    "errores_arca": errors,
                },
                sort_keys=True,
            ),
        }
    )
    attempt = rows["intentos_emision_fiscal"][0]
    authorized_successor = {
        **attempt,
        "id": 702,
        "operacion_id": 201,
        "guarda_rece_id": 601,
        "duplicados_generacion_id": 302,
    }
    attempt.update(
        {
            "estado": "rechazado_arca",
            "categoria_error": vps_migration.ARCA_RECHAZO_GLOBAL_CATEGORIA,
            "errores_arca_json": json.dumps(errors, sort_keys=True),
            "comprobante_id": None,
            "cae": None,
            "cae_vencimiento": None,
        }
    )
    rows["intentos_emision_fiscal"].append(authorized_successor)
    successor_association = {
        **rows["operaciones_idempotentes_elegibilidad_rece"][-1],
        "id": 143,
        "operacion_id": 201,
    }
    rows["operaciones_idempotentes_elegibilidad_rece"].append(successor_association)
    next(row for row in rows["operaciones_idempotentes"] if row["id"] == 201)[
        "rece_snapshot_hash"
    ] = vps_migration._digest_asociaciones_rece(
        [{**successor_association, "punto_venta_numero": 6}]
    )
    rows["puntos_venta_guardas_emision_rece"].append(
        {
            **rows["puntos_venta_guardas_emision_rece"][0],
            "id": 601,
            "operacion_id": 201,
        }
    )


def _apply_v4_partial_batch_global_rejection(
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Conserva A autorizado y el 10005 posterior de B en la misma operación."""
    lote_row = next(row for row in rows["lotes_comprobantes"] if row["id"] == 100)
    errors = [dict(item) for item in vps_migration.ARCA_RECHAZO_GLOBAL_ERRORES]
    metadata = {
        "pf19c_rechazo_global": {
            "operacion_id": 200,
            "categoria": vps_migration.ARCA_RECHAZO_GLOBAL_CATEGORIA,
            "grupos_rechazo_ids": [156],
            "grupos_no_enviados_ids": [],
            "errores_arca": errors,
        }
    }
    lote_row["metadata_json"] = json.dumps(metadata, sort_keys=True)
    lote = _v4_lote_replay_payload(lote_row)
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    operation.update(
        {
            "estado": "rechazado_arca",
            "response_json": json.dumps(
                {
                    "lote": lote,
                    "mensaje": vps_migration.ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE,
                    "en_progreso": False,
                    "errores_arca": errors,
                },
                sort_keys=True,
            ),
        }
    )
    authorized = next(
        row for row in rows["intentos_emision_fiscal"] if row["id"] == 700
    )
    rows["intentos_emision_fiscal"].append(
        {
            **authorized,
            "id": 702,
            "numero_planificado": 179,
            "payload_hash": "b" * 64,
            "huella_logica": "c" * 64,
            "estado": "rechazado_arca",
            "categoria_error": vps_migration.ARCA_RECHAZO_GLOBAL_CATEGORIA,
            "mensaje": vps_migration.ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE,
            "errores_arca_json": json.dumps(errors, sort_keys=True),
            "comprobante_id": None,
            "cae": None,
            "cae_vencimiento": None,
            "grupo_id": 156,
            "duplicados_generacion_id": None,
        }
    )


def test_manifest_v4_preserva_clausura_pf13_y_convierte_tipos(tmp_path: Path) -> None:
    package, _, _ = _build_v4_package(tmp_path)

    manifest = vps_migration.load_and_verify_manifest(package)
    operations = vps_migration.read_package_rows(
        package,
        manifest,
        "operaciones_idempotentes",
    )
    generations = vps_migration.read_package_rows(
        package,
        manifest,
        "lotes_duplicados_evidencias",
    )

    assert manifest["package_version"] == 4
    assert manifest["closure"]["preserved_lote_ids"] == [90, 100]
    assert len(manifest["closure"]["preserved_group_ids"]) == 101
    assert manifest["closure"]["preserved_group_ids"][:2] == [91, 101]
    assert manifest["closure"]["preserved_group_ids"][-1] == 200
    assert manifest["closure"]["generation_ids"] == [300, 301, 302]
    assert operations[0]["lote_id"] is None
    assert [row["lote_id"] for row in operations[1:]] == [100, 100, 90, None]
    assert isinstance(operations[1]["control_duplicados_json"], dict)
    assert generations[0]["aceptada_at"].utcoffset() == timedelta(0)
    generations_200 = [row for row in generations if row["operacion_id"] == 200]
    assert [row["generacion"] for row in generations_200] == [1, 2]
    assert operations[1]["duplicados_generacion_id"] == 301
    attempts = vps_migration.read_package_rows(
        package, manifest, "intentos_emision_fiscal"
    )
    assert (
        next(row for row in attempts if row["id"] == 700)["duplicados_generacion_id"]
        == 300
    )
    assert next(row for row in attempts if row["id"] == 701)["guarda_rece_id"] is None
    assert generations_200[1]["aceptacion_origen_generacion_id"] == 300
    assert operations[2]["operacion_raiz_id"] == 200
    assert operations[3]["duplicados_version"] is None
    assert operations[4]["tipo_operacion"] == "emitir_comprobante"
    assert not any(
        row["operacion_id"] == 203
        for row in vps_migration.read_package_rows(
            package,
            manifest,
            "intentos_emision_fiscal",
        )
    )
    assert manifest["notes"] == list(vps_migration_v4.PACKAGE_NOTES)

    groups = vps_migration.read_package_rows(
        package, manifest, "lotes_comprobantes_grupos"
    )
    states = [row["estado"] for row in groups if row["lote_id"] == 100]
    assert len(states) == 100
    assert {state: states.count(state) for state in set(states)} == {
        "autorizado": 10,
        "autorizado_externo": 5,
        "cargado": 10,
        "validado": 15,
        "con_error": 15,
        "fallido": 25,
        "descartado": 20,
    }


@pytest.mark.parametrize(
    "created_at",
    [
        "2026-09-05T12:00:00",
        "2026-09-05T12:00:00Z",
        "2026-09-05T12:00:00+00:00",
        "2026-09-05T09:00:00-03:00",
    ],
    ids=["legacy-utc", "utc-z", "utc-offset", "offset-equivalente"],
)
def test_manifest_v4_preserva_replay_del_mismo_instante_utc(
    tmp_path: Path,
    created_at: str,
) -> None:
    """La comparación temporal no reescribe el replay ni metadatos opacos."""
    package, rows, manifest = _build_v4_package(tmp_path)
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    response = json.loads(operation["response_json"])
    opaque_metadata = {
        "hora_sin_procedencia": "2026-09-05T09:00:00",
        "historia": {"created_at": "2026-09-05T09:00:00-03:00"},
    }
    response["lote"]["created_at"] = created_at
    response["lote"]["metadata_json"] = opaque_metadata
    original_json = json.dumps(response, sort_keys=True)
    operation["response_json"] = original_json
    _write_v4_package(package, rows, previous_manifest=manifest)
    operations_path = package / "data" / "operaciones_idempotentes.jsonl"
    original_file = operations_path.read_bytes()
    original_rows = deepcopy(rows)

    loaded = vps_migration.load_and_verify_manifest(package)
    converted = vps_migration.read_package_rows(
        package, loaded, "operaciones_idempotentes"
    )
    replay = next(row for row in converted if row["id"] == 200)["response_json"]

    assert replay == json.loads(original_json)
    assert replay["lote"]["created_at"] == created_at
    assert replay["lote"]["metadata_json"] == opaque_metadata
    assert operations_path.read_bytes() == original_file
    assert rows == original_rows
    assert (
        next(row for row in rows["lotes_comprobantes"] if row["id"] == 100)[
            "created_at"
        ]
        == "2026-09-05 12:00:00"
    )


@pytest.mark.parametrize(
    "created_at",
    [
        "2026-09-05T12:00:00.000001Z",
        "2026-09-05T12:00:01Z",
        "2026-09-05T12:00:00-03:00",
    ],
    ids=["microsegundo-distinto", "segundo-distinto", "offset-otro-instante"],
)
def test_manifest_v4_rechaza_replay_con_otro_instante_utc(
    tmp_path: Path,
    created_at: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    response = json.loads(operation["response_json"])
    response["lote"]["created_at"] = created_at
    operation["response_json"] = json.dumps(response, sort_keys=True)
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="lote durable"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 90),
        ("empresa_id", 11),
        ("archivo_hash", "f" * 64),
        ("estado", "en_progreso"),
        ("formato_importacion_version_id", 62),
    ],
)
def test_manifest_v4_instante_equivalente_no_admite_lote_adulterado(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    response = json.loads(operation["response_json"])
    response["lote"]["created_at"] = "2026-09-05T09:00:00-03:00"
    response["lote"][field] = value
    operation["response_json"] = json.dumps(response, sort_keys=True)
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="Replay terminal v4"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "mutation",
    [
        "lote_preservado",
        "seleccion_original",
        "aceptacion_heredada",
        "intento_generacion",
        "grupo_faltante",
        "testigo_faltante",
    ],
)
def test_manifest_v4_rechaza_manipulacion_coordinada_del_grafo(
    tmp_path: Path,
    mutation: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    if mutation == "lote_preservado":
        rows["operaciones_idempotentes"][1]["lote_id"] = None
    elif mutation == "seleccion_original":
        control = json.loads(
            rows["operaciones_idempotentes"][1]["control_duplicados_json"]
        )
        control["seleccion_original"] = [{"grupo_id": 102}]
        rows["operaciones_idempotentes"][1]["control_duplicados_json"] = json.dumps(
            control, sort_keys=True
        )
    elif mutation == "aceptacion_heredada":
        rows["lotes_duplicados_evidencias"][1]["aceptacion_id"] = "otra-aceptacion"
    elif mutation == "intento_generacion":
        rows["intentos_emision_fiscal"][0]["duplicados_generacion_id"] = 302
    elif mutation == "grupo_faltante":
        rows["lotes_comprobantes_grupos"] = [
            row for row in rows["lotes_comprobantes_grupos"] if row["id"] != 101
        ]
    else:
        rows["lotes_duplicados_coincidencias_miembros"].pop()
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_replay_terminal_incompatible_recalculado(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    rows["operaciones_idempotentes"][1]["response_json"] = json.dumps(
        {"incompatible": True}, sort_keys=True
    )
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="(?i)replay terminal v4"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_notas_legacy_incompatibles(tmp_path: Path) -> None:
    package, _, manifest = _build_v4_package(tmp_path)
    manifest["notes"] = list(vps_migration_v3.PACKAGE_NOTES)
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(vps_migration.MigrationError, match="notes"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_intento_autorizado_fiscalmente_incompatible(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    rows["intentos_emision_fiscal"][0].update(
        {"cae": "99999999999999", "total": "999.99"}
    )
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="(?i)intento autorizado v4"):
        vps_migration.load_and_verify_manifest(package)


def _agregar_intento_individual_v4(
    rows: dict[str, list[dict[str, Any]]],
    *,
    attempt_id: int,
    state: str,
    marker: str,
) -> None:
    template = next(row for row in rows["intentos_emision_fiscal"] if row["id"] == 701)
    attempt = {
        **template,
        "id": attempt_id,
        "operacion_id": 203,
        "lote_id": None,
        "grupo_id": None,
        "duplicados_generacion_id": None,
        "payload_hash": marker * 64,
        "huella_logica": marker * 64,
        "estado": state,
    }
    if state != "autorizado":
        attempt.update(
            {
                "comprobante_id": None,
                "cae": None,
                "cae_vencimiento": None,
                "categoria_error": vps_migration.LEGACY_PF19_CATEGORIA,
            }
        )
    rows["intentos_emision_fiscal"].append(attempt)


def test_manifest_v4_rechaza_dos_autorizaciones_individuales(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _agregar_intento_individual_v4(
        rows,
        attempt_id=703,
        state="autorizado",
        marker="b",
    )
    _agregar_intento_individual_v4(
        rows,
        attempt_id=704,
        state="autorizado",
        marker="c",
    )
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="autorización única"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_admite_autorizacion_unica_con_historia_negativa(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _agregar_intento_individual_v4(
        rows,
        attempt_id=703,
        state="autorizado",
        marker="b",
    )
    _agregar_intento_individual_v4(
        rows,
        attempt_id=704,
        state="fallido_verificado",
        marker="c",
    )
    _write_v4_package(package, rows, previous_manifest=manifest)

    loaded = vps_migration.load_and_verify_manifest(package)

    assert loaded["package_version"] == 4


def test_manifest_v4_rechaza_puntero_de_generacion_atrasado(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    control = json.loads(operation["control_duplicados_json"])
    operation["duplicados_generacion_id"] = 300
    control["duplicados_generacion_id"] = 300
    control["duplicados_generacion"] = 1
    operation["control_duplicados_json"] = json.dumps(control, sort_keys=True)
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="generación seleccionada"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_sucesor_pf19c_con_raiz_independiente(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _apply_v4_pf19c_rejection_with_successor(rows)
    successor = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 201
    )
    successor["operacion_raiz_id"] = 201
    generation = next(
        row for row in rows["lotes_duplicados_evidencias"] if row["id"] == 302
    )
    generation["aceptacion_origen_generacion_id"] = 302
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="historia terminal"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_casos_hermanos_del_replay_terminal(
    tmp_path: Path,
) -> None:
    package, base_rows, manifest = _build_v4_package(tmp_path)

    def remove_response(rows: dict[str, list[dict[str, Any]]]) -> None:
        rows["operaciones_idempotentes"][1]["response_json"] = None

    def cross_lot(rows: dict[str, list[dict[str, Any]]]) -> None:
        response = json.loads(rows["operaciones_idempotentes"][1]["response_json"])
        response["lote"]["id"] = 90
        rows["operaciones_idempotentes"][1]["response_json"] = json.dumps(
            response, sort_keys=True
        )

    def contradict_state(rows: dict[str, list[dict[str, Any]]]) -> None:
        rows["operaciones_idempotentes"][1]["estado"] = "rechazado_arca"

    def wrong_retry_shape(rows: dict[str, list[dict[str, Any]]]) -> None:
        response = json.loads(rows["operaciones_idempotentes"][2]["response_json"])
        response["en_progreso"] = False
        rows["operaciones_idempotentes"][2]["response_json"] = json.dumps(
            response, sort_keys=True
        )

    for mutation in (
        remove_response,
        cross_lot,
        contradict_state,
        wrong_retry_shape,
    ):
        rows = deepcopy(base_rows)
        mutation(rows)
        _write_v4_package(package, rows, previous_manifest=manifest)
        with pytest.raises(vps_migration.MigrationError):
            vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_cada_campo_fiscal_durable_del_intento(
    tmp_path: Path,
) -> None:
    package, base_rows, manifest = _build_v4_package(tmp_path)
    mutations = {
        "cae": "99999999999999",
        "cae_vencimiento": "2026-09-16",
        "numero_planificado": 999,
        "fecha_emision": "2026-09-06",
        "total": "999.99",
        "tipo_comprobante": 11,
        "punto_venta_id": 41,
        "empresa_id": 11,
        "estado": "fallido_verificado",
    }
    for field_name, value in mutations.items():
        rows = deepcopy(base_rows)
        rows["intentos_emision_fiscal"][0][field_name] = value
        _write_v4_package(package, rows, previous_manifest=manifest)
        with pytest.raises(vps_migration.MigrationError):
            vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize("state", ["fallido_verificado", "rechazado_arca"])
def test_manifest_v4_rechaza_intento_negativo_con_evidencia_positiva(
    tmp_path: Path,
    state: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    rows["intentos_emision_fiscal"][0]["estado"] = state
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="evidencia positiva"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_admite_rechazo_global_con_sucesor_autorizado(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _apply_v4_pf19c_rejection_with_successor(rows)
    _write_v4_package(package, rows, previous_manifest=manifest)

    loaded = vps_migration.load_and_verify_manifest(package)

    assert loaded["package_version"] == 4
    rejection = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 200
    )
    successor = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 201
    )
    assert successor["tipo_operacion"] == "reintentar_fallidos_lote"
    assert successor["operacion_raiz_id"] == rejection["operacion_raiz_id"] == 200


def test_manifest_v4_admite_batch_parcial_con_autorizacion_antes_de_10005(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _apply_v4_partial_batch_global_rejection(rows)
    _write_v4_package(package, rows, previous_manifest=manifest)

    loaded = vps_migration.load_and_verify_manifest(package)
    attempts = vps_migration.read_package_rows(
        package,
        loaded,
        "intentos_emision_fiscal",
    )

    assert loaded["package_version"] == 4
    assert {
        (row["grupo_id"], row["estado"])
        for row in attempts
        if row["operacion_id"] == 200
    } == {(101, "autorizado"), (156, "rechazado_arca")}


@pytest.mark.parametrize(
    "mutation",
    ["comprobante", "cae", "grupo", "guarda", "generacion"],
)
def test_manifest_v4_batch_parcial_no_relaja_evidencia_autorizada(
    tmp_path: Path,
    mutation: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _apply_v4_partial_batch_global_rejection(rows)
    authorized = next(
        row for row in rows["intentos_emision_fiscal"] if row["id"] == 700
    )
    if mutation == "comprobante":
        authorized["comprobante_id"] = 110
    elif mutation == "cae":
        authorized["cae"] = "99999999999999"
    elif mutation == "grupo":
        authorized["grupo_id"] = 102
    elif mutation == "guarda":
        authorized["guarda_rece_id"] = None
    else:
        authorized["duplicados_generacion_id"] = 302
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_no_amplia_autorizacion_individual_a_estado_no_finalizado(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    individual = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 203
    )
    individual["estado"] = "fallido"
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_rechazo_global_sin_sucesor_durable(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _apply_v4_pf19c_rejection_with_successor(rows)
    rows["intentos_emision_fiscal"].pop()
    rows["puntos_venta_guardas_emision_rece"].pop()
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(vps_migration.MigrationError, match="historia terminal"):
        vps_migration.load_and_verify_manifest(package)


def _invalidar_evidencia_autorizada(
    row: dict[str, Any],
    mutation: str,
    *,
    number_field: str,
) -> None:
    if mutation == "numero_cero":
        row[number_field] = 0
    elif mutation == "cae_vacio":
        row["cae"] = ""
    else:
        row["cae_vencimiento"] = None


@pytest.mark.parametrize(
    "mutation",
    ["numero_cero", "cae_vacio", "vencimiento_ausente"],
)
def test_evidencia_fiscal_minima_replay_individual_coordinado(
    tmp_path: Path,
    mutation: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    operation = next(
        row for row in rows["operaciones_idempotentes"] if row["id"] == 203
    )
    response = json.loads(operation["response_json"])
    receipt = next(row for row in rows["comprobantes"] if row["id"] == 110)
    _invalidar_evidencia_autorizada(response, mutation, number_field="numero")
    _invalidar_evidencia_autorizada(receipt, mutation, number_field="numero")
    operation["response_json"] = json.dumps(response, sort_keys=True)
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(
        vps_migration.MigrationError,
        match="Replay terminal v4 exitoso sin evidencia fiscal completa",
    ):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "mutation",
    ["numero_cero", "cae_vacio", "vencimiento_ausente"],
)
def test_evidencia_fiscal_minima_intento_autorizado_coordinado(
    tmp_path: Path,
    mutation: str,
) -> None:
    _, rows, _ = _build_v4_package(tmp_path)
    attempt = next(row for row in rows["intentos_emision_fiscal"] if row["id"] == 700)
    receipt = next(row for row in rows["comprobantes"] if row["id"] == 111)
    group = next(row for row in rows["lotes_comprobantes_grupos"] if row["id"] == 101)
    _invalidar_evidencia_autorizada(
        attempt,
        mutation,
        number_field="numero_planificado",
    )
    _invalidar_evidencia_autorizada(receipt, mutation, number_field="numero")
    if mutation != "vencimiento_ausente":
        _invalidar_evidencia_autorizada(
            group,
            mutation,
            number_field="numero_asignado",
        )

    with pytest.raises(
        vps_migration.MigrationError,
        match="Intento autorizado v4 sin evidencia fiscal completa",
    ):
        vps_migration._validate_v4_attempt_fiscal_evidence(rows)


@pytest.mark.parametrize(
    "mutation",
    ["numero_cero", "cae_vacio", "vencimiento_ausente"],
)
def test_evidencia_fiscal_minima_grupo_autorizado_coordinado(
    tmp_path: Path,
    mutation: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    group = next(row for row in rows["lotes_comprobantes_grupos"] if row["id"] == 111)
    receipt = next(row for row in rows["comprobantes"] if row["id"] == 121)
    if mutation != "vencimiento_ausente":
        _invalidar_evidencia_autorizada(
            group,
            mutation,
            number_field="numero_asignado",
        )
    _invalidar_evidencia_autorizada(receipt, mutation, number_field="numero")
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(
        vps_migration.MigrationError,
        match="Un grupo v4 perdió su evidencia fiscal",
    ):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "mutation",
    ["numero_cero", "cae_vacio", "vencimiento_ausente"],
)
def test_evidencia_fiscal_minima_comprobante_autorizado_aislado(
    tmp_path: Path,
    mutation: str,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    receipt = {
        **next(row for row in rows["comprobantes"] if row["id"] == 125),
        "id": 999,
    }
    _invalidar_evidencia_autorizada(receipt, mutation, number_field="numero")
    rows["comprobantes"].append(receipt)
    _write_v4_package(package, rows, previous_manifest=manifest)

    with pytest.raises(
        vps_migration.MigrationError,
        match="Comprobante autorizado v4 sin evidencia fiscal completa",
    ):
        vps_migration.load_and_verify_manifest(package)


def test_postflight_v4_ejecuta_validacion_fiscal_sobre_snapshot_igual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    rows["intentos_emision_fiscal"][0]["cae"] = "99999999999999"
    manifest = _write_v4_package(package, rows, previous_manifest=manifest)
    monkeypatch.setattr(
        vps_migration, "validate_target_alembic_head", lambda *args: None
    )
    monkeypatch.setattr(vps_migration, "validate_v3_coordinators", lambda *args: None)
    monkeypatch.setattr(vps_migration, "scalar_count", lambda *args: 0)
    monkeypatch.setattr(
        vps_migration,
        "read_database_rows",
        lambda _conn, table_name: rows[table_name],
    )

    with pytest.raises(vps_migration.MigrationError, match="Intento autorizado v4"):
        vps_migration.validate_imported_database(
            object(), manifest, rows, vps_migration_v4.V4_CONTRACT
        )


def test_captura_v4_selecciona_lotes_comparables_y_normaliza_solo_legacy(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    _apply_v4_partial_batch_global_rejection(rows)
    _write_v4_package(package, rows, previous_manifest=manifest)
    manifest = vps_migration.load_and_verify_manifest(package)
    package_rows = {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in vps_migration_v4.INCLUDED_TABLES
    }
    source_path = tmp_path / "source-v4.db"
    engine = create_engine(f"sqlite:///{source_path}", future=True)
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            conn.execute(
                text("INSERT INTO alembic_version VALUES (:version)"),
                {"version": vps_migration_v4.ALEMBIC_HEAD},
            )
            for table_name in vps_migration_v4.INSERT_ORDER:
                insert_rows = package_rows[table_name]
                deferred = vps_migration_v4.DEFERRED_COLUMNS.get(table_name, ())
                if deferred:
                    insert_rows = [
                        {**row, **{column_name: None for column_name in deferred}}
                        for row in insert_rows
                    ]
                if insert_rows:
                    conn.execute(Base.metadata.tables[table_name].insert(), insert_rows)
            vps_migration.restore_deferred_columns(
                conn,
                package_rows,
                vps_migration_v4.V4_CONTRACT,
            )
            omitted_lote = {
                **package_rows["lotes_comprobantes"][0],
                "id": 130,
                "nombre_archivo": "legacy-omitido.xlsx",
                "archivo_hash": "3" * 64,
            }
            conn.execute(
                Base.metadata.tables["lotes_comprobantes"].insert(), omitted_lote
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(lote_id=130)
            )
            conn.execute(
                Base.metadata.tables["lotes_duplicados_coordinacion"].insert(),
                [
                    {"empresa_id": 10, "ambiente": "homologacion", "revision": 9},
                    {"empresa_id": 10, "ambiente": "produccion", "revision": 7},
                ],
            )
        connection = sqlite3.connect(source_path)
        connection.row_factory = sqlite3.Row
        try:
            vps_migration.validate_v4_sqlite_schema(connection)
            preflight = vps_migration.run_preflight_on_connection(
                connection,
                db_path=source_path,
                certs_base=package / "certs",
                repo_head=vps_migration_v4.ALEMBIC_HEAD,
            )
            capture = vps_migration.capture_v4_rows(connection)
        finally:
            connection.close()
    finally:
        engine.dispose()

    exported = vps_migration.export_package(
        source_db=source_path,
        certs_dir=package / "certs",
        output_root=tmp_path / "export-v4",
        target_key_password="clave-v4-destino",
        source_key_password="clave-v3-sintetica",
        source_quiesced=True,
    )
    exported_manifest = vps_migration.load_and_verify_manifest(exported)
    assert capture.closure["preserved_lote_ids"] == [90, 100]
    assert preflight.included_counts == capture.included_counts
    assert exported_manifest["package_version"] == 4
    assert len(capture.closure["preserved_group_ids"]) == 101
    assert capture.normalization["pairs"] == [
        {
            "operacion_id": 140,
            "lote_id": 130,
            "grupo_ids": [],
            "grupos_rechazo_ids": [],
            "grupos_no_enviados_ids": [],
        }
    ]
    assert capture.rows["operaciones_idempotentes"][0]["lote_id"] is None
    assert capture.rows["operaciones_idempotentes"][1]["lote_id"] == 100
    assert {
        (row["grupo_id"], row["estado"])
        for row in capture.rows["intentos_emision_fiscal"]
        if row["operacion_id"] == 200
    } == {(101, "autorizado"), (156, "rechazado_arca")}


def test_barrera_v4_cubre_campos_pf13_no_usados_por_la_clausura(
    tmp_path: Path,
) -> None:
    package, rows, manifest = _build_v4_package(tmp_path)
    rows["lotes_comprobantes"][1]["mensaje_resumen"] = "contenido alterado"
    path = package / "data" / "lotes_comprobantes.jsonl"
    raw = b"".join(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
        ).encode("utf-8")
        for row in rows["lotes_comprobantes"]
    )
    path.write_bytes(raw)
    manifest["data_files"]["lotes_comprobantes"].update(
        {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    )
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(vps_migration.MigrationError, match="barrera idempotente v4"):
        vps_migration.load_and_verify_manifest(package)


def test_destino_v4_sucio_bloquea_antes_de_importar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, _, _ = _build_v4_package(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    contract = vps_migration.select_import_contract(manifest)
    counted: list[str] = []
    monkeypatch.setattr(
        vps_migration,
        "validate_target_alembic_head",
        lambda *args: None,
    )
    monkeypatch.setattr(
        vps_migration,
        "validate_v4_target_table_contract",
        lambda *args: None,
    )
    monkeypatch.setattr(
        vps_migration,
        "validate_canonical_target_seeds",
        lambda *args: None,
    )

    def count(_conn: Any, table_name: str) -> int:
        counted.append(table_name)
        return int(table_name == "lotes_duplicados_coordinacion")

    monkeypatch.setattr(vps_migration, "scalar_count", count)

    with pytest.raises(vps_migration.MigrationError, match="destino no está limpia"):
        vps_migration.ensure_target_database_ready(object(), manifest, contract)

    assert set(counted) == set(contract.target_empty_tables)


def _build_historical_v3_package(tmp_path: Path) -> Path:
    """Materializa un grafo v3 derivado del blob histórico 61ac23b8."""
    package = tmp_path / "historical-v3"
    data_dir = package / "data"
    certs_dir = package / "certs"
    data_dir.mkdir(parents=True)
    certs_dir.mkdir()

    timestamp = "2026-06-03 12:00:00"
    lote_response = _lote_response_payload()
    operation_response = {
        "lote": lote_response,
        "mensaje": "Lote procesado",
        "en_progreso": False,
    }
    rece_material = {
        "version": 1,
        "contextos": [
            {
                "empresa_id": 10,
                "punto_venta_id": 40,
                "punto_venta_numero": 6,
                "ambiente": "produccion",
                "elegibilidad_revision_id": 42,
                "punto_venta_revision_fiscal": 1,
            }
        ],
    }
    rece_sha = hashlib.sha256(
        json.dumps(
            rece_material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    rows: dict[str, list[dict[str, Any]]] = {
        "empresas": [
            {
                "id": 10,
                "razon_social": "Empresa Sintética SA",
                "cuit": "20123456789",
                "condicion_iva": "Responsable Inscripto",
                "ingresos_brutos": None,
                "domicilio": "Calle de prueba 123",
                "localidad": "Ciudad de prueba",
                "provincia": "Buenos Aires",
                "codigo_postal": "1000",
                "email": "prueba@example.test",
                "telefono": None,
                "inicio_actividades": "2020-01-01",
                "logo": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        ],
        "usuarios": [
            {
                "id": 20,
                "email": "admin@example.test",
                "hashed_password": "hash-sintetico-no-utilizable",
                "nombre": "Operador Sintético",
                "activo": 1,
                "es_admin": 1,
                "puede_crear_editar_emisores": 1,
                "empresa_id": 10,
                "created_at": timestamp,
                "updated_at": timestamp,
                "ultimo_login": None,
                "password_changed_at": None,
            }
        ],
        "usuario_emisor_acceso": [
            {
                "usuario_id": 20,
                "empresa_id": 10,
                "otorgado_por_usuario_id": 20,
                "origen": "migracion_legacy",
                "otorgado_en": timestamp,
            }
        ],
        "clientes": [
            {
                "id": 30,
                "razon_social": "Cliente Sintético",
                "tipo_documento": "CUIT",
                "numero_documento": "20999999991",
                "condicion_iva": "Consumidor Final",
                "domicilio": None,
                "localidad": None,
                "provincia": None,
                "codigo_postal": None,
                "email": None,
                "telefono": None,
                "notas": None,
                "activo": 1,
                "empresa_id": 10,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        ],
        "puntos_venta": [
            {
                "id": 40,
                "numero": 6,
                "nombre": "PV sintético",
                "sistema": "RECE",
                "domicilio": None,
                "domicilio_fuente": None,
                "nombre_fantasia": None,
                "nombre_fantasia_fuente": None,
                "es_webservice": 1,
                "bloqueado": 0,
                "fecha_baja": None,
                "fuente": "manual",
                "activo": 1,
                "usar_en_factuflow": 1,
                "revision_fiscal": 1,
                "ultima_comprobacion_arca_en": timestamp,
                "empresa_id": 10,
                "created_at": timestamp,
            }
        ],
        "puntos_venta_elegibilidad_rece_revisiones": [
            {
                "id": 41,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "homologacion",
                "revision": 1,
                "estado": "no_verificado",
                "fuente": "edicion",
                "evidencia_tipo": "sin_evidencia",
                "evidencia_sha256": None,
                "clasificador_version": None,
                "empresa_cuit_snapshot": "20123456789",
                "punto_venta_numero_snapshot": 6,
                "punto_revision_fiscal": 1,
                "documento_emitido_en": None,
                "vigente_hasta": None,
                "observado_en": timestamp,
                "verificado_en": None,
                "creado_por_usuario_id": 20,
                "actor_usuario_id_snapshot": 20,
                "created_at": timestamp,
            },
            {
                "id": 42,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "revision": 1,
                "estado": "verificado_rece",
                "fuente": "constancia_arca_atestada",
                "evidencia_tipo": "rece_aplicativo_web_services_v1",
                "evidencia_sha256": "e" * 64,
                "clasificador_version": "rece-v1",
                "empresa_cuit_snapshot": "20123456789",
                "punto_venta_numero_snapshot": 6,
                "punto_revision_fiscal": 1,
                "documento_emitido_en": "2026-06-03",
                "vigente_hasta": "2027-06-03",
                "observado_en": timestamp,
                "verificado_en": timestamp,
                "creado_por_usuario_id": 20,
                "actor_usuario_id_snapshot": 20,
                "created_at": timestamp,
            },
        ],
        "puntos_venta_elegibilidad_rece_actual": [
            {
                "id": 43,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "homologacion",
                "revision_actual_id": 41,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
            {
                "id": 44,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "revision_actual_id": 42,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ],
        "operaciones_idempotentes": [
            {
                "id": 140,
                "idempotency_key": "v3-lote-sintetico",
                "tipo_operacion": "procesar_lote",
                "payload_hash": "b" * 64,
                "estado": "finalizado",
                "response_json": json.dumps(operation_response, ensure_ascii=False),
                "error_json": None,
                "rece_snapshot_hash": rece_sha,
                "lote_id": None,
                "created_at": timestamp,
                "updated_at": timestamp,
                "empresa_id": 10,
                "usuario_id": 20,
            }
        ],
        "operaciones_idempotentes_elegibilidad_rece": [
            {
                "id": 141,
                "operacion_id": 140,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "elegibilidad_revision_id": 42,
                "punto_venta_revision_fiscal": 1,
                "created_at": timestamp,
            }
        ],
        "certificados": [
            {
                "id": 50,
                "nombre": "Certificado sintético",
                "cuit": "20123456789",
                "fecha_emision": "2026-05-01",
                "fecha_vencimiento": "2030-05-01",
                "archivo_crt": "synthetic-50.crt",
                "archivo_key": "synthetic-50.key",
                "activo": 1,
                "ambiente": "produccion",
                "empresa_id": 10,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        ],
        "formatos_importacion": [
            {
                "id": 60,
                "nombre": "Formato sintético",
                "descripcion": "Formato histórico de prueba",
                "alcance": "empresa",
                "activo": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
                "empresa_id": 10,
            }
        ],
        "formatos_importacion_versiones": [
            {
                "id": 61,
                "version": 1,
                "estado": "vigente",
                "configuracion_json": json.dumps(
                    {"agrupacion": "fila", "campos": {}}, ensure_ascii=False
                ),
                "headers_firma_json": json.dumps(
                    {"requeridos": ["Fecha"]}, ensure_ascii=False
                ),
                "created_at": timestamp,
                "formato_id": 60,
            }
        ],
        "formatos_importacion_campos": [
            {
                "id": 62,
                "campo_destino": "fecha_emision",
                "origen_tipo": "header",
                "encabezado": "Fecha",
                "alias_json": json.dumps(["Fecha", "Fecha emisión"]),
                "letra_columna": None,
                "indice_columna": None,
                "valor_constante_json": None,
                "requerido": 1,
                "transformacion": "fecha",
                "valor_default_json": None,
                "created_at": timestamp,
                "version_id": 61,
            }
        ],
        "formatos_importacion_reglas": [
            {
                "id": 63,
                "nombre": "Una fila por comprobante",
                "tipo": "agrupacion",
                "configuracion_json": json.dumps({"modo": "fila"}),
                "orden": 1,
                "activo": 1,
                "created_at": timestamp,
                "version_id": 61,
            }
        ],
        "perfiles_carga_masiva": [
            {
                "id": 70,
                "nombre": "Perfil sintético",
                "descripcion": "Perfil histórico de prueba",
                "configuracion_json": json.dumps(
                    {"formato_importacion_id": 60}, ensure_ascii=False
                ),
                "es_predeterminado": 1,
                "activo": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
                "empresa_id": 10,
            }
        ],
        "comprobantes": [
            {
                "id": 110,
                "tipo_comprobante": 6,
                "concepto": 1,
                "numero": 123,
                "fecha_emision": "2026-06-03",
                "fecha_vencimiento": None,
                "fecha_servicio_desde": None,
                "fecha_servicio_hasta": None,
                "fecha_vto_pago": None,
                "subtotal": "100.00",
                "descuento": "0.00",
                "iva_21": "21.00",
                "iva_10_5": "0.00",
                "iva_27": "0.00",
                "otros_impuestos": "0.00",
                "total": "121.00",
                "cae": "12345678901234",
                "cae_vencimiento": "2026-06-13",
                "estado": "autorizado",
                "origen_emision": "lote",
                "moneda": "PES",
                "cotizacion": "1.000000",
                "observaciones": None,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "cliente_id": 30,
                "receptor_tipo_documento": 80,
                "receptor_numero_documento": "20999999991",
                "receptor_razon_social": "Cliente Sintético",
                "receptor_condicion_iva": "Consumidor Final",
                "receptor_domicilio": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        ],
        "comprobante_items": [
            {
                "id": 120,
                "codigo": "SYN-1",
                "descripcion": "Ítem sintético",
                "cantidad": "1.0000",
                "unidad": "unidades",
                "precio_unitario": "100.0000",
                "descuento_porcentaje": "0.00",
                "iva_porcentaje": "21.00",
                "subtotal": "100.00",
                "orden": 1,
                "comprobante_id": 110,
            }
        ],
    }
    historical_tables = (
        "empresas",
        "usuarios",
        "usuario_emisor_acceso",
        "clientes",
        "puntos_venta",
        "puntos_venta_elegibilidad_rece_revisiones",
        "puntos_venta_elegibilidad_rece_actual",
        "operaciones_idempotentes",
        "operaciones_idempotentes_elegibilidad_rece",
        "certificados",
        "formatos_importacion",
        "formatos_importacion_versiones",
        "formatos_importacion_campos",
        "formatos_importacion_reglas",
        "perfiles_carga_masiva",
        "comprobantes",
        "comprobante_items",
    )
    assert tuple(rows) == historical_tables

    raw_key = tmp_path / "synthetic-50.raw.key"
    _write_certificate_pair(
        certs_dir / "synthetic-50.crt",
        raw_key,
        cuit="20123456789",
        not_before=datetime(2026, 5, 1),
        not_after=datetime(2030, 5, 1),
    )
    vps_migration.reencrypt_private_key(
        raw_key,
        certs_dir / "synthetic-50.key",
        "clave-v3-sintetica",
    )
    raw_key.unlink()
    data_files: dict[str, dict[str, Any]] = {}
    for table_name in historical_tables:
        path = data_dir / f"{table_name}.jsonl"
        raw = b"".join(
            (
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            ).encode("utf-8")
            for row in rows[table_name]
        )
        path.write_bytes(raw)
        data_files[table_name] = {
            "path": f"data/{table_name}.jsonl",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows[table_name]),
            "bytes": len(raw),
        }

    env_path = package / "env.production.required.example"
    env_path.write_text(
        "\n".join(
            [
                "# Plantilla privada para restaurar el paquete en VPS.",
                "# Reemplazar todos los valores antes de operar producción.",
                "APP_SECRET_KEY=<generar-clave-larga>",
                "ARCA_PRIVATE_KEY_PASSWORD=<misma-clave-usada-al-exportar>",
                "POSTGRES_DB=factuflow",
                "POSTGRES_USER=factuflow",
                "POSTGRES_PASSWORD=<password-fuerte>",
                "ARCA_ENV=produccion",
                "CORS_ORIGINS=https://factuflow.tu-dominio.com",
                "VITE_API_URL=https://factuflow.tu-dominio.com",
                "CERTS_PATH=./certs",
                "",
            ]
        ),
        encoding="utf-8",
    )
    pairs = [
        {
            "operacion_id": 140,
            "lote_id": 130,
            "grupo_ids": [],
            "grupos_rechazo_ids": [],
            "grupos_no_enviados_ids": [],
        }
    ]
    pairs_sha = hashlib.sha256(
        json.dumps(
            pairs,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    source_barrier = {
        "source_quiesced": True,
        "sqlite_transaction": "BEGIN IMMEDIATE",
        "data_version": 0,
    }
    normalization = {
        "rule": "set_null_preserve_source_pairs_and_group_inventory_sha256_v2",
        "rows": 1,
        "sha256": pairs_sha,
        "pairs": pairs,
    }
    excluded_tables = (
        "intentos_emision_fiscal",
        "resoluciones_legacy_pf19_journal",
        "puntos_venta_guardas_emision_rece",
        "lotes_comprobantes",
        "lotes_comprobantes_grupos",
        "lotes_comprobantes_filas",
        "lotes_comprobantes_eventos",
        "eventos_sistema",
        "exportaciones_almacenamiento",
    )
    excluded_counts = {table_name: 0 for table_name in excluded_tables}
    excluded_counts["lotes_comprobantes"] = 1
    safe_omitted = {
        "blockers": 0,
        "excluded_counts": excluded_counts,
        "operaciones_terminales_preservadas": 1,
        "operaciones_lote_normalizado": 1,
        "asociaciones_rece_preservadas": 1,
        "intentos_terminales_omitidos": 0,
        "resoluciones_legacy_pf19_omitidas": 0,
        "guardas_terminales_omitidas": 0,
        "lotes_seguros_omitidos": 1,
        "grupos_seguros_omitidos": 0,
        "filas_omitidas": 0,
        "eventos_lote_omitidos": 0,
        "eventos_sistema_omitidos": 0,
        "exportaciones_omitidas": 0,
    }
    barrier_material = {
        "version": 1,
        "algorithm": "sha256-json-c14n-v1",
        "source_barrier": source_barrier,
        "normalization": normalization,
        "operations": [
            {
                "id": 140,
                "empresa_id": 10,
                "idempotency_key": "v3-lote-sintetico",
                "tipo_operacion": "procesar_lote",
                "payload_hash": "b" * 64,
                "estado": "finalizado",
                "response_json": operation_response,
                "rece_snapshot_hash": rece_sha,
                "lote_id": None,
            }
        ],
        "associations": [
            {
                "id": 141,
                "operacion_id": 140,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "elegibilidad_revision_id": 42,
                "punto_venta_revision_fiscal": 1,
            }
        ],
    }
    barrier_sha = hashlib.sha256(
        json.dumps(
            barrier_material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    counts = {table_name: len(table_rows) for table_name, table_rows in rows.items()}
    certificate_files = {}
    for filename in ("synthetic-50.crt", "synthetic-50.key"):
        path = certs_dir / filename
        certificate_files[filename] = {
            "path": f"certs/{filename}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "package_version": 3,
        "created_at": "2026-09-05T12:00:00+00:00",
        "scope": "operacion_futura_con_comprobantes",
        "alembic_version": "f4a5b6c7d8e9",
        "included_tables": list(historical_tables),
        "excluded_tables": list(excluded_tables),
        "target_empty_tables": [
            "empresas",
            "usuarios",
            "usuario_emisor_acceso",
            "clientes",
            "puntos_venta",
            "puntos_venta_elegibilidad_rece_revisiones",
            "puntos_venta_elegibilidad_rece_actual",
            "operaciones_idempotentes",
            "operaciones_idempotentes_elegibilidad_rece",
            "certificados",
            "perfiles_carga_masiva",
            "comprobantes",
            "comprobante_items",
            *excluded_tables,
        ],
        "included_counts": counts,
        "excluded_counts": excluded_counts,
        "active_certificates": 1,
        "safe_omitted": safe_omitted,
        "normalizations": {"operaciones_idempotentes.lote_id": normalization},
        "source_barrier": source_barrier,
        "idempotency_barrier": {
            "version": 1,
            "algorithm": "sha256-json-c14n-v1",
            "rows": 1,
            "sha256": barrier_sha,
        },
        "data_files": data_files,
        "certificate_files": certificate_files,
        "env_template": {
            "path": "env.production.required.example",
            "sha256": hashlib.sha256(env_path.read_bytes()).hexdigest(),
            "bytes": env_path.stat().st_size,
        },
        "required_env_keys": [
            "APP_SECRET_KEY",
            "ARCA_PRIVATE_KEY_PASSWORD",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "ARCA_ENV",
            "CORS_ORIGINS",
            "VITE_API_URL",
            "CERTS_PATH",
        ],
        "notes": [
            "No incluye lotes, filas, temporales, PDFs, Excels, logs ni cache ARCA.",
            "Las claves privadas se re-cifraron con ARCA_PRIVATE_KEY_PASSWORD destino.",
            "La SQLite local debe conservarse como evidencia histórica privada.",
        ],
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return package


def _historical_v3_operation_row() -> dict[str, Any]:
    return {
        "id": 1,
        "idempotency_key": "historical-v3",
        "tipo_operacion": "emitir_comprobante",
        "payload_hash": "a" * 64,
        "estado": "fallido_verificado",
        "response_json": None,
        "error_json": None,
        "rece_snapshot_hash": None,
        "lote_id": None,
        "created_at": "2026-09-05 12:00:00",
        "updated_at": "2026-09-05 12:00:00",
        "empresa_id": 1,
        "usuario_id": None,
    }


def test_lector_historico_v3_acepta_fixture_material_independiente(
    tmp_path: Path,
) -> None:
    package = _build_historical_v3_package(tmp_path)

    manifest = vps_migration.load_and_verify_manifest(package)
    package_rows = {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in vps_migration_v3.INCLUDED_TABLES
    }
    vps_migration.verify_package_certificates(
        package,
        manifest,
        "clave-v3-sintetica",
        package_rows,
    )

    assert manifest["alembic_version"] == "f4a5b6c7d8e9"
    assert set(manifest["data_files"]) == set(vps_migration_v3.V3_COLUMNS)
    assert manifest["included_counts"]["empresas"] == 1
    assert manifest["included_counts"]["operaciones_idempotentes"] == 1
    assert manifest["included_counts"]["formatos_importacion"] == 1
    assert manifest["included_counts"]["formatos_importacion_versiones"] == 1
    assert manifest["included_counts"]["formatos_importacion_campos"] == 1
    assert manifest["included_counts"]["formatos_importacion_reglas"] == 1
    assert manifest["included_counts"]["perfiles_carga_masiva"] == 1
    assert manifest["included_counts"]["comprobante_items"] == 1
    assert manifest["active_certificates"] == 1
    assert package_rows["operaciones_idempotentes"][0]["lote_id"] is None
    assert all(
        package_rows["operaciones_idempotentes"][0][column] is None
        for column in vps_migration_v3.TARGET_NULL_ADDITIONS["operaciones_idempotentes"]
    )
    assert package_rows["formatos_importacion_versiones"][0]["configuracion_json"] == {
        "agrupacion": "fila",
        "campos": {},
    }
    assert package_rows["formatos_importacion_campos"][0]["alias_json"] == [
        "Fecha",
        "Fecha emisión",
    ]
    assert package_rows["formatos_importacion_reglas"][0]["configuracion_json"] == {
        "modo": "fila"
    }
    assert package_rows["perfiles_carga_masiva"][0]["configuracion_json"] == {
        "formato_importacion_id": 60
    }
    assert manifest["normalizations"]["operaciones_idempotentes.lote_id"]["pairs"] == [
        {
            "operacion_id": 140,
            "lote_id": 130,
            "grupo_ids": [],
            "grupos_rechazo_ids": [],
            "grupos_no_enviados_ids": [],
        }
    ]


def test_exportador_no_rotula_v3_desde_schema_pf13(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vps_migration, "get_repo_alembic_head", lambda *_: "head-pf13")

    with pytest.raises(vps_migration.MigrationError, match="exportación v4 PF-13"):
        vps_migration.export_package(
            source_db=tmp_path / "no-se-lee.db",
            certs_dir=tmp_path / "no-se-lee-certs",
            output_root=tmp_path / "no-se-crea",
            target_key_password="clave-sintetica",
            source_quiesced=True,
        )

    assert not (tmp_path / "no-se-crea").exists()


def test_lector_v3_no_depende_de_globales_mutables_del_exportador(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    monkeypatch.setattr(vps_migration, "INCLUDED_TABLES", ["tabla_v4"])
    monkeypatch.setattr(vps_migration, "EXCLUDED_TABLES", ["otra_tabla_v4"])
    monkeypatch.setattr(vps_migration, "TARGET_EMPTY_TABLES", ["tabla_v4"])
    monkeypatch.setattr(vps_migration, "MANIFEST_TOP_LEVEL_KEYS", {"campo_v4"})
    monkeypatch.setattr(vps_migration, "SAFE_OMITTED_KEYS", {"campo_v4"})
    monkeypatch.setattr(vps_migration, "OPERATION_LOTE_NORMALIZATION_RULE", "v4")
    monkeypatch.setattr(vps_migration, "IDEMPOTENCY_BARRIER_ALGORITHM", "v4")

    manifest = vps_migration.load_and_verify_manifest(package)

    assert manifest["package_version"] == 3


def test_import_v3_selecciona_contrato_en_precarga_locks_postflight_y_secuencias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    monkeypatch.setattr(vps_migration, "INCLUDED_TABLES", ["tabla_v4"])
    monkeypatch.setattr(vps_migration, "EXCLUDED_TABLES", ["excluida_v4"])
    monkeypatch.setattr(vps_migration, "TARGET_EMPTY_TABLES", ["tabla_v4"])
    monkeypatch.setattr(vps_migration, "SEEDED_INCLUDED_TABLES", ["tabla_v4"])
    monkeypatch.setattr(
        vps_migration,
        "V3_ADAPTER_TARGET_EMPTY_TABLES",
        ["tabla_v4"],
    )

    manifest = vps_migration.load_and_verify_manifest(package)
    contract = vps_migration.select_import_contract(manifest)
    package_rows = {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in contract.included_tables
    }

    class Result:
        def __init__(self, scalar_value: Any = None, row: Any = None) -> None:
            self.scalar_value = scalar_value
            self.row = row

        def scalar(self) -> Any:
            return self.scalar_value

        def one(self) -> Any:
            return self.row

    class Connection:
        def __init__(self) -> None:
            self.statements: list[str] = []
            self.sequence_tables: list[str] = []

        def execute(self, statement: Any, parameters: Any = None) -> Result:
            rendered = str(statement)
            self.statements.append(rendered)
            if "pg_get_serial_sequence" in rendered:
                table_name = parameters["table_name"]
                self.sequence_tables.append(table_name)
                return Result(f"public.{table_name}_id_seq")
            if "max(" in rendered.lower():
                return Result(None)
            if "last_value" in rendered:
                return Result(row=(1, False))
            return Result()

    conn = Connection()
    vps_migration.lock_target_tables_for_import(conn, contract)
    assert "tabla_v4" not in conn.statements[-1]
    assert '"empresas"' in conn.statements[-1]

    counted_tables: list[str] = []
    monkeypatch.setattr(
        vps_migration, "validate_target_alembic_head", lambda *args: None
    )
    monkeypatch.setattr(
        vps_migration, "validate_canonical_target_seeds", lambda conn: None
    )
    monkeypatch.setattr(
        vps_migration,
        "scalar_count",
        lambda conn, table_name: counted_tables.append(table_name) or 0,
    )
    vps_migration.ensure_target_database_ready(conn, manifest, contract)
    assert set(counted_tables) == set(
        contract.target_empty_tables + contract.adapter_target_empty_tables
    )

    vps_migration.clear_seeded_included_tables(conn, contract)
    assert all(
        any(table_name in statement for statement in conn.statements)
        for table_name in contract.seeded_included_tables
    )

    read_tables: list[str] = []
    monkeypatch.setattr(
        vps_migration,
        "read_database_rows",
        lambda conn, table_name: read_tables.append(table_name)
        or package_rows[table_name],
    )
    monkeypatch.setattr(vps_migration, "validate_v3_coordinators", lambda *args: None)
    vps_migration.validate_imported_database(
        conn,
        manifest,
        package_rows,
        contract,
    )
    assert tuple(read_tables) == contract.included_tables

    conn.sequence_tables.clear()
    vps_migration.reset_postgres_sequences(conn, contract)
    assert tuple(conn.sequence_tables) == contract.sequence_tables
    conn.sequence_tables.clear()
    vps_migration.verify_postgres_sequences(conn, contract)
    assert tuple(conn.sequence_tables) == contract.sequence_tables


def test_replay_v3_no_depende_de_dtos_vigentes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DtoV4Incompatible:
        @classmethod
        def model_validate(cls, value: Any) -> Any:
            raise AssertionError("el loader v3 consultó un DTO vigente")

    for name in (
        "EmitirComprobanteResponse",
        "LoteComprobanteResponse",
        "LoteProcesamientoResponse",
        "LoteAccionResponse",
    ):
        monkeypatch.setattr(vps_migration, name, DtoV4Incompatible)

    package = _build_historical_v3_package(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    table_rows = {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in vps_migration_v3.INCLUDED_TABLES
    }
    table_rows["operaciones_idempotentes"][0].update(
        {
            "tipo_operacion": "emitir_comprobante",
            "response_json": {
                "exito": True,
                "comprobante_id": 110,
                "tipo_comprobante": 6,
                "punto_venta": 6,
                "numero": 123,
                "fecha": "2026-06-03",
                "cae": "12345678901234",
                "cae_vencimiento": "2026-06-13",
                "total": "121.00",
                "mensaje": "Comprobante autorizado",
            },
        }
    )
    vps_migration._validate_packaged_terminal_operations(
        table_rows=table_rows,
        normalization_pairs=[],
    )


def test_replay_v3_rechaza_campos_futuros() -> None:
    individual = {
        "exito": False,
        "tipo_comprobante": 6,
        "punto_venta": 6,
        "numero": 0,
        "fecha": "2026-06-03",
        "total": "0.00",
        "mensaje": "No autorizado",
        "campo_v4": None,
    }
    batch = {
        "lote": _lote_response_payload(),
        "mensaje": "Lote procesado",
        "en_progreso": False,
        "campo_v4": None,
    }

    with pytest.raises(ValueError, match="shape de replay v3"):
        vps_migration_v3.parse_individual_replay(individual)
    with pytest.raises(ValueError, match="shape de replay v3"):
        vps_migration_v3.parse_batch_replay(batch, operation_type="procesar_lote")
    with pytest.raises(ValueError, match="shape de replay v3"):
        vps_migration_v3.parse_batch_error_replay(
            {"categoria_error": "fallo", "campo_v4": None}
        )


def test_schema_v3_congela_dimensiones_y_representabilidad() -> None:
    key_spec = vps_migration_v3.V3_COLUMNS["operaciones_idempotentes"][
        "idempotency_key"
    ]
    total_spec = vps_migration_v3.V3_COLUMNS["comprobantes"]["total"]
    timestamp_spec = vps_migration_v3.V3_COLUMNS["empresas"]["created_at"]

    assert (key_spec.length, total_spec.precision, total_spec.scale) == (128, 12, 2)
    assert timestamp_spec.timezone is False
    assert vps_migration_v3.validate_value(total_spec, "1.2300") == Decimal("1.2300")
    with pytest.raises(ValueError, match="longitud histórica"):
        vps_migration_v3.validate_value(key_spec, "x" * 129)
    with pytest.raises(ValueError, match="requiere redondeo"):
        vps_migration_v3.validate_value(total_spec, "1.234")
    with pytest.raises(ValueError, match="precisión histórica"):
        vps_migration_v3.validate_value(total_spec, "12345678901.00")
    with pytest.raises(ValueError, match="zona horaria"):
        vps_migration_v3.validate_value(
            timestamp_spec,
            "2026-06-03T12:00:00+00:00",
        )


def test_parser_v3_rechaza_valores_no_representables_antes_del_destino(
    tmp_path: Path,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    mutations = (
        ("operaciones_idempotentes", "idempotency_key", "x" * 129),
        ("comprobantes", "total", "1.234"),
        ("empresas", "created_at", "2026-06-03T12:00:00+00:00"),
    )
    for table_name, column_name, value in mutations:
        path = package / "data" / f"{table_name}.jsonl"
        row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        row[column_name] = value
        serialized = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        with pytest.raises(vps_migration.MigrationError, match="Tipo JSONL"):
            vps_migration._parse_manifest_jsonl_lines(
                [serialized],
                table_name=table_name,
            )


def test_schema_v3_congela_acciones_fk_y_compatibilidad_destino(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for table_name in vps_migration_v3.INCLUDED_TABLES:
        vps_migration.validate_v3_target_table_contract(
            table_name,
            Base.metadata.tables[table_name],
        )
    access_actions = {
        foreign_key.local_columns: foreign_key.ondelete
        for foreign_key in vps_migration_v3.FOREIGN_KEYS["usuario_emisor_acceso"]
    }
    assert access_actions == {
        ("usuario_id",): "CASCADE",
        ("empresa_id",): "CASCADE",
        ("otorgado_por_usuario_id",): "SET NULL",
    }
    assert all(
        foreign_key.onupdate is None
        for foreign_keys in vps_migration_v3.FOREIGN_KEYS.values()
        for foreign_key in foreign_keys
    )

    target_type = (
        Base.metadata.tables["operaciones_idempotentes"].c["idempotency_key"].type
    )
    monkeypatch.setattr(target_type, "length", 127)
    with pytest.raises(vps_migration.MigrationError, match="tipo físico"):
        vps_migration.validate_v3_target_table_contract(
            "operaciones_idempotentes",
            Base.metadata.tables["operaciones_idempotentes"],
        )

    user_table = Base.metadata.tables["usuarios"]
    user_company_fk = next(
        constraint
        for constraint in user_table.foreign_key_constraints
        if tuple(element.parent.name for element in constraint.elements)
        == ("empresa_id",)
    )
    monkeypatch.setattr(user_company_fk, "ondelete", "CASCADE")
    with pytest.raises(vps_migration.MigrationError, match="FK física"):
        vps_migration.validate_v3_target_table_contract("usuarios", user_table)


@pytest.mark.parametrize("mutation", ["null", "duplicate", "reordered"])
def test_pk_compuesta_v3_exige_forma_canonica(mutation: str) -> None:
    first = {
        "usuario_id": 20,
        "empresa_id": 10,
        "otorgado_por_usuario_id": 20,
        "origen": "migracion_legacy",
        "otorgado_en": "2026-06-03 12:00:00",
    }
    second = {**first, "empresa_id": 11}
    if mutation == "null":
        rows = [{**first, "usuario_id": None}]
    elif mutation == "duplicate":
        rows = [first, dict(first)]
    else:
        rows = [second, first]
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows]

    with pytest.raises(vps_migration.MigrationError, match="PK|NULL"):
        vps_migration._parse_manifest_jsonl_lines(
            lines,
            table_name="usuario_emisor_acceso",
        )


def test_lector_v3_rechaza_fk_manipulada_con_hash_reatestiguado(
    tmp_path: Path,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    access_path = package / "data" / "usuario_emisor_acceso.jsonl"
    access = json.loads(access_path.read_text(encoding="utf-8"))
    access["empresa_id"] = 999
    raw = (json.dumps(access, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    access_path.write_bytes(raw)
    manifest["data_files"]["usuario_emisor_acceso"].update(
        {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(vps_migration.MigrationError, match="FK incluida inexistente"):
        vps_migration.load_and_verify_manifest(package)


def test_lector_v3_rechaza_normalizacion_reatestiguada_incompatible(
    tmp_path: Path,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    normalization = manifest["normalizations"]["operaciones_idempotentes.lote_id"]
    normalization["pairs"][0]["lote_id"] = 999
    normalization["sha256"] = hashlib.sha256(
        json.dumps(
            normalization["pairs"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(vps_migration.MigrationError, match="lote de replay"):
        vps_migration.load_and_verify_manifest(package)


def test_lector_historico_v3_rechaza_head_y_columnas_pf13(
    tmp_path: Path,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["alembic_version"] = vps_migration.get_repo_alembic_head()
    vps_migration.write_json(manifest_path, manifest)

    with pytest.raises(vps_migration.MigrationError, match="head Alembic"):
        vps_migration.load_and_verify_manifest(package)

    row = _historical_v3_operation_row()
    row["control_duplicados_json"] = None
    serialized = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    with pytest.raises(vps_migration.MigrationError, match="Schema JSONL"):
        vps_migration._parse_manifest_jsonl_lines(
            [serialized], table_name="operaciones_idempotentes"
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("package_version", 4, "Versión de paquete"),
        ("package_version", 3.0, "Versión de paquete"),
        ("included_tables", ["empresas"], "included_tables"),
        ("excluded_tables", [], "excluded_tables"),
        ("target_empty_tables", ["empresas"], "target_empty_tables"),
    ],
)
def test_lector_v3_rechaza_version_o_particion_arbitraria(
    tmp_path: Path,
    field: str,
    value: Any,
    message: str,
) -> None:
    package = _build_historical_v3_package(tmp_path)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(vps_migration.MigrationError, match=message):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    ("column", "value"),
    [("id", "1"), ("idempotency_key", None), ("created_at", "no-es-fecha")],
)
def test_lector_historico_v3_rechaza_tipo_o_nulabilidad(
    column: str,
    value: Any,
) -> None:
    row = _historical_v3_operation_row()
    row[column] = value
    serialized = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"

    with pytest.raises(vps_migration.MigrationError):
        vps_migration._parse_manifest_jsonl_lines(
            [serialized], table_name="operaciones_idempotentes"
        )


def test_adaptador_v3_agrega_solo_nulls_pf13_y_planifica_coordinadores() -> None:
    adapted = vps_migration_v3.adapt_row(
        "operaciones_idempotentes", _historical_v3_operation_row()
    )

    assert set(adapted) == {
        *vps_migration_v3.V3_COLUMNS["operaciones_idempotentes"],
        *vps_migration_v3.TARGET_NULL_ADDITIONS["operaciones_idempotentes"],
    }
    assert all(
        adapted[column] is None
        for column in vps_migration_v3.TARGET_NULL_ADDITIONS["operaciones_idempotentes"]
    )
    assert adapted["lote_id"] is None
    assert vps_migration_v3.coordinator_plan([{"id": 3}, {"id": 1}]) == [
        {"empresa_id": 1, "ambiente": "homologacion", "revision": 0},
        {"empresa_id": 1, "ambiente": "produccion", "revision": 0},
        {"empresa_id": 3, "ambiente": "homologacion", "revision": 0},
        {"empresa_id": 3, "ambiente": "produccion", "revision": 0},
    ]


def test_precarga_v3_adapta_al_destino_vigente(tmp_path: Path) -> None:
    row = _historical_v3_operation_row()
    raw = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    package = tmp_path / "package"
    data_dir = package / "data"
    data_dir.mkdir(parents=True)
    path = data_dir / "operaciones_idempotentes.jsonl"
    path.write_bytes(raw)
    manifest = {
        "package_version": 3,
        "data_files": {
            "operaciones_idempotentes": {
                "path": "data/operaciones_idempotentes.jsonl",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "rows": 1,
            }
        },
    }

    adapted = vps_migration.read_package_rows(
        package, manifest, "operaciones_idempotentes"
    )

    assert adapted[0]["id"] == 1
    assert adapted[0]["created_at"] == datetime(2026, 9, 5, 12, 0, 0)
    assert all(
        adapted[0][column] is None
        for column in vps_migration_v3.TARGET_NULL_ADDITIONS["operaciones_idempotentes"]
    )


def test_fk_v3_no_depende_de_constraints_del_orm_vigente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = {table_name: [] for table_name in vps_migration_v3.INCLUDED_TABLES}
    rows["empresas"] = [{"id": 1}]
    rows["usuarios"] = [{"id": 2, "empresa_id": 999}]
    monkeypatch.setattr(vps_migration, "Base", object())

    with pytest.raises(vps_migration.MigrationError, match="FK incluida inexistente"):
        vps_migration._validate_packaged_foreign_keys(rows)


def _insert_group_and_row(
    db_path: Path,
    *,
    group_state: str = "validado",
    row_state: str = "validado",
    authorized_evidence: bool = False,
    include_comprobante: bool = True,
    legacy_snapshot: bool = False,
) -> None:
    """Agrega un grupo y una fila legacy omitibles al lote fuente."""
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["lotes_comprobantes_grupos"].insert(),
                {
                    "id": 160,
                    "comprobante_ref": "VPS-1",
                    "orden": 1,
                    "estado": group_state,
                    "tipo_comprobante": 6,
                    "punto_venta_numero": 6,
                    "total_estimado": Decimal("121.00"),
                    "payload_json": {"fecha_emision": "2026-06-03"},
                    "mensajes_json": [],
                    "cae": "12345678901234" if authorized_evidence else None,
                    "numero_asignado": 123 if authorized_evidence else None,
                    "empresa_id": 10,
                    "punto_venta_id": (
                        40 if authorized_evidence and not legacy_snapshot else None
                    ),
                    "ambiente": (
                        "produccion"
                        if authorized_evidence and not legacy_snapshot
                        else None
                    ),
                    "punto_venta_elegibilidad_revision_id": (
                        42 if authorized_evidence and not legacy_snapshot else None
                    ),
                    "punto_venta_revision_fiscal": (
                        1 if authorized_evidence and not legacy_snapshot else None
                    ),
                    "comprobante_id": (
                        110 if authorized_evidence and include_comprobante else None
                    ),
                    "lote_id": 130,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes_filas"].insert(),
                {
                    "id": 161,
                    "fila_excel": 2,
                    "comprobante_ref": "VPS-1",
                    "estado": row_state,
                    "datos_json": {"fecha_emision": "2026-06-03"},
                    "mensajes_json": [],
                    "lote_id": 130,
                    "grupo_id": 160,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
    finally:
        engine.dispose()


def _rece_digest() -> str:
    """Calcula independientemente el digest RECE del contexto sintético."""
    material = {
        "version": 1,
        "contextos": [
            {
                "empresa_id": 10,
                "punto_venta_id": 40,
                "punto_venta_numero": 6,
                "ambiente": "produccion",
                "elegibilidad_revision_id": 45,
                "punto_venta_revision_fiscal": 1,
            }
        ],
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _insert_terminal_guard_context(db_path: Path, *, with_attempt: bool) -> None:
    """Agrega una operación RECE cerrada pre-ARCA con guarda durable."""
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables[
                    "puntos_venta_elegibilidad_rece_revisiones"
                ].insert(),
                {
                    "id": 45,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": "produccion",
                    "revision": 2,
                    "estado": "verificado_rece",
                    "fuente": "constancia_arca_atestada",
                    "evidencia_tipo": "rece_aplicativo_web_services_v1",
                    "evidencia_sha256": "e" * 64,
                    "clasificador_version": "rece-v1",
                    "empresa_cuit_snapshot": "20123456789",
                    "punto_venta_numero_snapshot": 6,
                    "punto_revision_fiscal": 1,
                    "documento_emitido_en": date(2026, 6, 3),
                    "vigente_hasta": date(2027, 6, 3),
                    "observado_en": datetime(2026, 6, 3, 12, 0, 0),
                    "verificado_en": datetime(2026, 6, 3, 12, 0, 0),
                    "creado_por_usuario_id": 20,
                    "actor_usuario_id_snapshot": 20,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"].c.id
                    == 44
                )
                .values(revision_actual_id=45)
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"].insert(),
                {
                    "id": 140,
                    "idempotency_key": "vps-guarda-terminal",
                    "tipo_operacion": "emitir_comprobante",
                    "payload_hash": "b" * 64,
                    "estado": "fallido_verificado",
                    "response_json": {
                        "exito": False,
                        "comprobante_id": None,
                        "tipo_comprobante": 6,
                        "punto_venta": 6,
                        "numero": 124,
                        "fecha": "2026-06-03",
                        "cae": None,
                        "cae_vencimiento": None,
                        "total": "121.00",
                        "mensaje": "Cierre pre-ARCA verificado",
                        "errores": ["No se solicitó CAE"],
                        "requiere_reconciliacion": False,
                        "categoria_error": "pre_arca_verificado",
                    },
                    "rece_snapshot_hash": _rece_digest(),
                    "empresa_id": 10,
                    "usuario_id": 20,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables[
                    "operaciones_idempotentes_elegibilidad_rece"
                ].insert(),
                {
                    "id": 141,
                    "operacion_id": 140,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": "produccion",
                    "elegibilidad_revision_id": 45,
                    "punto_venta_revision_fiscal": 1,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["puntos_venta_guardas_emision_rece"].insert(),
                {
                    "id": 142,
                    "token": "g" * 64,
                    "fase": "cerrada_pre_arca",
                    "operacion_id": 140,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": "produccion",
                    "elegibilidad_revision_id": 45,
                    "punto_venta_revision_fiscal": 1,
                    "cerrada_en": datetime(2026, 6, 3, 12, 1, 0),
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 1, 0),
                },
            )
            if with_attempt:
                conn.execute(
                    Base.metadata.tables["intentos_emision_fiscal"].insert(),
                    {
                        "id": 143,
                        "tipo_comprobante": 6,
                        "punto_venta_numero": 6,
                        "numero_planificado": 124,
                        "fecha_emision": date(2026, 6, 3),
                        "total": Decimal("121.00"),
                        "payload_hash": "c" * 64,
                        "huella_logica": "d" * 64,
                        "estado": "fallido_verificado",
                        "categoria_error": "pre_arca_verificado",
                        "mensaje": "No se solicitó CAE",
                        "ambiente": "produccion",
                        "punto_venta_elegibilidad_revision_id": 45,
                        "punto_venta_revision_fiscal": 1,
                        "guarda_rece_id": 142,
                        "operacion_id": 140,
                        "empresa_id": 10,
                        "usuario_id": 20,
                        "punto_venta_id": 40,
                        "created_at": datetime(2026, 6, 3, 12, 0, 0),
                        "updated_at": datetime(2026, 6, 3, 12, 1, 0),
                    },
                )
    finally:
        engine.dispose()


def _authorize_terminal_guard_context(
    db_path: Path,
    *,
    publish_success: bool,
) -> None:
    """Convierte la guarda sintética en evidencia terminal post-ARCA."""
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["puntos_venta_guardas_emision_rece"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_guardas_emision_rece"].c.id
                    == 142
                )
                .values(
                    fase="cerrada_terminal",
                    arca_iniciada_en=datetime(2026, 6, 3, 12, 0, 30),
                    cerrada_en=datetime(2026, 6, 3, 12, 1, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"]
                .update()
                .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                .values(
                    estado="autorizado",
                    comprobante_id=110,
                    numero_planificado=123,
                    cae="12345678901234",
                    cae_vencimiento=date(2026, 6, 13),
                    categoria_error=None,
                    mensaje="Comprobante autorizado",
                )
            )
            if publish_success:
                conn.execute(
                    Base.metadata.tables["operaciones_idempotentes"]
                    .update()
                    .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                    .values(
                        estado="finalizado",
                        response_json=_individual_success_response(),
                    )
                )
    finally:
        engine.dispose()


def _individual_success_response(**overrides: Any) -> dict[str, Any]:
    """Construye el replay individual exitoso del comprobante incluido."""
    response: dict[str, Any] = {
        "exito": True,
        "comprobante_id": 110,
        "tipo_comprobante": 6,
        "punto_venta": 6,
        "numero": 123,
        "fecha": "2026-06-03",
        "cae": "12345678901234",
        "cae_vencimiento": "2026-06-13",
        "total": "121.00",
        "mensaje": "Comprobante autorizado",
        "errores": [],
        "requiere_reconciliacion": False,
        "categoria_error": None,
    }
    response.update(overrides)
    return response


def _individual_global_rejection_response() -> dict[str, Any]:
    """Construye el DTO sanitario del rechazo global PF-19C."""
    return {
        "exito": False,
        "comprobante_id": None,
        "tipo_comprobante": 6,
        "punto_venta": 6,
        "numero": 124,
        "fecha": "2026-06-03",
        "cae": None,
        "cae_vencimiento": None,
        "total": "121.00",
        "mensaje": "ARCA rechazó el requerimiento completo antes de autorizar.",
        "errores": [
            "Revisá la habilitación RECE del punto de venta antes de iniciar otra emisión."
        ],
        "errores_arca": [
            {
                "codigo": 10005,
                "alcance": "global",
                "mensaje": "El punto de venta no está dado de alta como RECE en ARCA.",
            }
        ],
        "requiere_reconciliacion": False,
        "categoria_error": "arca_rechazo_global_excluyente",
    }


def _canonical_json_sha256(value: dict[str, Any]) -> str:
    """Reproduce la huella canónica append-only del replay legacy PF-19C."""
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _batch_global_rejection_response(*, operation_id: int = 140) -> dict[str, Any]:
    """Construye el replay batch autocontenido del rechazo global PF-19C."""
    errores_arca = _individual_global_rejection_response()["errores_arca"]
    marker = {
        "operacion_id": operation_id,
        "categoria": "arca_rechazo_global_excluyente",
        "grupos_rechazo_ids": [160],
        "grupos_no_enviados_ids": [],
        "errores_arca": errores_arca,
    }
    lote = _lote_response_payload()
    lote.update(
        {
            "estado": "fallido",
            "grupos_validos": 0,
            "grupos_emitidos": 0,
            "grupos_fallidos": 1,
            "mensaje_resumen": (
                "ARCA rechazó un requerimiento completo y FactuFlow detuvo los "
                "grupos restantes sin enviarlos."
            ),
            "metadata_json": {"pf19c_rechazo_global": marker},
            "finished_at": "2026-06-03T12:01:00",
        }
    )
    return {
        "lote": lote,
        "mensaje": lote["mensaje_resumen"],
        "en_progreso": False,
        "errores_arca": errores_arca,
    }


def _insert_pf19c_global_rejection(db_path: Path) -> None:
    """Convierte el contexto sintético en un rechazo global terminal exacto."""
    _insert_terminal_guard_context(db_path, with_attempt=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["puntos_venta_guardas_emision_rece"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_guardas_emision_rece"].c.id
                    == 142
                )
                .values(
                    fase="cerrada_terminal",
                    arca_iniciada_en=datetime(2026, 6, 3, 12, 0, 30),
                    cerrada_en=datetime(2026, 6, 3, 12, 1, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"]
                .update()
                .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                .values(
                    estado="rechazado_arca",
                    categoria_error="arca_rechazo_global_excluyente",
                    errores_arca_json=_individual_global_rejection_response()[
                        "errores_arca"
                    ],
                    mensaje="ARCA rechazó el requerimiento completo antes de autorizar.",
                )
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(
                    estado="rechazado_arca",
                    response_json=_individual_global_rejection_response(),
                )
            )
    finally:
        engine.dispose()


def _insert_pf19c_batch_global_rejection(db_path: Path) -> None:
    """Persiste un 10005 batch con lote, grupo, intento y replay coherentes."""
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _insert_group_and_row(db_path, group_state="fallido", row_state="fallido")
    response = _batch_global_rejection_response()
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["puntos_venta_guardas_emision_rece"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_guardas_emision_rece"].c.id
                    == 142
                )
                .values(
                    fase="cerrada_terminal",
                    arca_iniciada_en=datetime(2026, 6, 3, 12, 0, 30),
                    cerrada_en=datetime(2026, 6, 3, 12, 1, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes_grupos"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes_grupos"].c.id == 160)
                .values(
                    punto_venta_id=40,
                    ambiente="produccion",
                    punto_venta_elegibilidad_revision_id=45,
                    punto_venta_revision_fiscal=1,
                )
            )
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"]
                .update()
                .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                .values(
                    estado="rechazado_arca",
                    categoria_error="arca_rechazo_global_excluyente",
                    errores_arca_json=response["errores_arca"],
                    mensaje="ARCA rechazó el requerimiento completo antes de autorizar.",
                    lote_id=130,
                    grupo_id=160,
                )
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes"].c.id == 130)
                .values(
                    estado="fallido",
                    grupos_validos=0,
                    grupos_emitidos=0,
                    grupos_fallidos=1,
                    mensaje_resumen=response["mensaje"],
                    metadata_json=response["lote"]["metadata_json"],
                    finished_at=datetime(2026, 6, 3, 12, 1, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(
                    tipo_operacion="procesar_lote",
                    lote_id=130,
                    estado="rechazado_arca",
                    response_json=response,
                )
            )
    finally:
        engine.dispose()


def _insert_pf19c_batch_success_after_global_rejection(db_path: Path) -> None:
    """Superpone una autorización batch B sin borrar la evidencia histórica A."""
    _insert_pf19c_batch_global_rejection(db_path)
    marker = _batch_global_rejection_response()["lote"]["metadata_json"]
    lote_response = _lote_response_payload()
    lote_response.update(
        {
            "metadata_json": marker,
            "finished_at": "2026-06-03T12:03:00",
            "updated_at": "2026-06-03T12:03:00",
        }
    )
    response = {
        "lote": lote_response,
        "mensaje": "El grupo fallido fue autorizado sin repetir el rechazo anterior.",
        "errores_arca": [],
    }
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"].insert(),
                {
                    "id": 240,
                    "idempotency_key": "vps-reintento-pf19c-b",
                    "tipo_operacion": "reintentar_fallidos_lote",
                    "payload_hash": "f" * 64,
                    "estado": "finalizado",
                    "response_json": response,
                    "rece_snapshot_hash": _rece_digest(),
                    "lote_id": 130,
                    "empresa_id": 10,
                    "usuario_id": 20,
                    "created_at": datetime(2026, 6, 3, 12, 2, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 3, 0),
                },
            )
            conn.execute(
                Base.metadata.tables[
                    "operaciones_idempotentes_elegibilidad_rece"
                ].insert(),
                {
                    "id": 241,
                    "operacion_id": 240,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": "produccion",
                    "elegibilidad_revision_id": 45,
                    "punto_venta_revision_fiscal": 1,
                    "created_at": datetime(2026, 6, 3, 12, 2, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["puntos_venta_guardas_emision_rece"].insert(),
                {
                    "id": 242,
                    "token": "h" * 64,
                    "fase": "cerrada_terminal",
                    "operacion_id": 240,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": "produccion",
                    "elegibilidad_revision_id": 45,
                    "punto_venta_revision_fiscal": 1,
                    "arca_iniciada_en": datetime(2026, 6, 3, 12, 2, 30),
                    "cerrada_en": datetime(2026, 6, 3, 12, 3, 0),
                    "created_at": datetime(2026, 6, 3, 12, 2, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 3, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"].insert(),
                {
                    "id": 243,
                    "tipo_comprobante": 6,
                    "punto_venta_numero": 6,
                    "numero_planificado": 123,
                    "fecha_emision": date(2026, 6, 3),
                    "total": Decimal("121.00"),
                    "payload_hash": "1" * 64,
                    "huella_logica": "2" * 64,
                    "estado": "autorizado",
                    "mensaje": "Comprobante autorizado",
                    "cae": "12345678901234",
                    "cae_vencimiento": date(2026, 6, 13),
                    "comprobante_id": 110,
                    "ambiente": "produccion",
                    "punto_venta_elegibilidad_revision_id": 45,
                    "punto_venta_revision_fiscal": 1,
                    "guarda_rece_id": 242,
                    "operacion_id": 240,
                    "lote_id": 130,
                    "grupo_id": 160,
                    "empresa_id": 10,
                    "usuario_id": 20,
                    "punto_venta_id": 40,
                    "created_at": datetime(2026, 6, 3, 12, 2, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 3, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes"].c.id == 130)
                .values(
                    estado="completado",
                    grupos_validos=1,
                    grupos_emitidos=1,
                    grupos_fallidos=0,
                    mensaje_resumen=None,
                    metadata_json=marker,
                    finished_at=datetime(2026, 6, 3, 12, 3, 0),
                    updated_at=datetime(2026, 6, 3, 12, 3, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes_grupos"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes_grupos"].c.id == 160)
                .values(
                    estado="autorizado",
                    mensajes_json=[],
                    cae="12345678901234",
                    numero_asignado=123,
                    comprobante_id=110,
                    updated_at=datetime(2026, 6, 3, 12, 3, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes_filas"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes_filas"].c.id == 161)
                .values(estado="autorizado", mensajes_json=[])
            )
    finally:
        engine.dispose()


def _insert_legacy_pf19_journal(db_path: Path) -> None:
    """Registra un cierre legacy PF-19 verificable y apto para omisión."""
    _insert_terminal_guard_context(db_path, with_attempt=True)
    response = _individual_success_response(
        exito=False,
        comprobante_id=None,
        numero=124,
        cae=None,
        cae_vencimiento=None,
        mensaje="Cierre legacy por ausencia de autorización verificada",
        errores=[],
        errores_arca=[],
        categoria_error="legacy_sin_autorizacion_verificada",
    )
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"]
                .update()
                .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                .values(
                    categoria_error="legacy_sin_autorizacion_verificada",
                    errores_arca_json=None,
                    mensaje="Cierre legacy por ausencia de autorización verificada",
                )
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(
                    estado="fallido_verificado",
                    response_json=response,
                )
            )
            conn.execute(
                Base.metadata.tables["resoluciones_legacy_pf19_journal"].insert(),
                {
                    "id": 170,
                    "accion": "cerrar_legacy_sin_autorizacion_verificada",
                    "plan_sha256": "1" * 64,
                    "terminal_response_sha256": _canonical_json_sha256(response),
                    "actor_usuario_id": 20,
                    "ambiente_consultado": "ambos",
                    "resultado": "legacy_sin_autorizacion_verificada",
                    "resultado_consultas_json": {
                        "homologacion": "ultimo_menor_al_planificado",
                        "produccion": "ultimo_menor_al_planificado",
                    },
                    "backup_metadata_json": {
                        "identificador": "backup-pf19c-001",
                        "timestamp": "2026-06-03T12:00:00Z",
                        "proposito": "cierre legacy pf19c",
                        "referencia_codigo": "commit-pf19c-001",
                    },
                    "backup_sha256": "2" * 64,
                    "intento_id": 143,
                    "empresa_id": 10,
                    "created_at": datetime(2026, 6, 3, 12, 1, 0),
                },
            )
    finally:
        engine.dispose()


def _insert_legacy_pf19_batch_journal(db_path: Path) -> None:
    """Registra un cierre legacy batch con replay y membresía exactos."""
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _insert_group_and_row(db_path, group_state="fallido", row_state="fallido")
    lote = _lote_response_payload()
    lote.update(
        {
            "estado": "fallido",
            "grupos_validos": 0,
            "grupos_emitidos": 0,
            "grupos_fallidos": 1,
            "mensaje_resumen": "Cierre legacy por ausencia de autorización verificada",
            "updated_at": "2026-06-03T12:01:00",
        }
    )
    response = {
        "lote": lote,
        "mensaje": "Cierre legacy por ausencia de autorización verificada",
        "en_progreso": False,
        "errores_arca": [],
    }
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["lotes_comprobantes_grupos"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes_grupos"].c.id == 160)
                .values(
                    punto_venta_id=40,
                    ambiente="produccion",
                    punto_venta_elegibilidad_revision_id=45,
                    punto_venta_revision_fiscal=1,
                )
            )
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"]
                .update()
                .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                .values(
                    estado="fallido_verificado",
                    categoria_error="legacy_sin_autorizacion_verificada",
                    errores_arca_json=None,
                    mensaje="Cierre legacy por ausencia de autorización verificada",
                    lote_id=130,
                    grupo_id=160,
                )
            )
            conn.execute(
                Base.metadata.tables["lotes_comprobantes"]
                .update()
                .where(Base.metadata.tables["lotes_comprobantes"].c.id == 130)
                .values(
                    estado="fallido",
                    grupos_validos=0,
                    grupos_emitidos=0,
                    grupos_fallidos=1,
                    mensaje_resumen=response["mensaje"],
                    updated_at=datetime(2026, 6, 3, 12, 1, 0),
                )
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(
                    tipo_operacion="procesar_lote",
                    lote_id=130,
                    estado="finalizado",
                    response_json=response,
                )
            )
            conn.execute(
                Base.metadata.tables["resoluciones_legacy_pf19_journal"].insert(),
                {
                    "id": 170,
                    "accion": "cerrar_legacy_sin_autorizacion_verificada",
                    "plan_sha256": "1" * 64,
                    "terminal_response_sha256": _canonical_json_sha256(response),
                    "actor_usuario_id": 20,
                    "ambiente_consultado": "ambos",
                    "resultado": "legacy_sin_autorizacion_verificada",
                    "resultado_consultas_json": {
                        "homologacion": "ultimo_menor_al_planificado",
                        "produccion": "ultimo_menor_al_planificado",
                    },
                    "backup_metadata_json": {
                        "identificador": "backup-pf19c-001",
                        "timestamp": "2026-06-03T12:00:00Z",
                        "proposito": "cierre legacy pf19c",
                        "referencia_codigo": "commit-pf19c-001",
                    },
                    "backup_sha256": "2" * 64,
                    "intento_id": 143,
                    "empresa_id": 10,
                    "created_at": datetime(2026, 6, 3, 12, 1, 0),
                },
            )
    finally:
        engine.dispose()


def _insert_foreign_comprobante(db_path: Path) -> None:
    """Agrega otro emisor con ledger válido y un comprobante autorizado."""
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["empresas"].insert(),
                {
                    "id": 11,
                    "razon_social": "Otro Emisor S.A.",
                    "cuit": "20999999991",
                    "condicion_iva": "RI",
                    "ingresos_brutos": "No informado",
                    "domicilio": "Av. Otro Emisor 456",
                    "localidad": "Buenos Aires",
                    "provincia": "Buenos Aires",
                    "codigo_postal": "1000",
                    "email": "otro-emisor@example.com",
                    "telefono": "456",
                    "inicio_actividades": date(2020, 1, 1),
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["lotes_duplicados_coordinacion"].insert(),
                [
                    {
                        "empresa_id": 11,
                        "ambiente": "homologacion",
                        "revision": 0,
                    },
                    {
                        "empresa_id": 11,
                        "ambiente": "produccion",
                        "revision": 0,
                    },
                ],
            )
            conn.execute(
                Base.metadata.tables["puntos_venta"].insert(),
                {
                    "id": 240,
                    "numero": 6,
                    "nombre": "Otro Web Services",
                    "es_webservice": True,
                    "bloqueado": False,
                    "activo": True,
                    "revision_fiscal": 1,
                    "empresa_id": 11,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            for revision_id, ambiente in ((241, "homologacion"), (242, "produccion")):
                conn.execute(
                    Base.metadata.tables[
                        "puntos_venta_elegibilidad_rece_revisiones"
                    ].insert(),
                    {
                        "id": revision_id,
                        "empresa_id": 11,
                        "punto_venta_id": 240,
                        "ambiente": ambiente,
                        "revision": 1,
                        "estado": "no_verificado",
                        "fuente": "migracion_legacy",
                        "evidencia_tipo": "sin_evidencia",
                        "punto_revision_fiscal": 1,
                        "observado_en": datetime(2026, 6, 3, 12, 0, 0),
                        "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    },
                )
            for head_id, ambiente, revision_id in (
                (243, "homologacion", 241),
                (244, "produccion", 242),
            ):
                conn.execute(
                    Base.metadata.tables[
                        "puntos_venta_elegibilidad_rece_actual"
                    ].insert(),
                    {
                        "id": head_id,
                        "empresa_id": 11,
                        "punto_venta_id": 240,
                        "ambiente": ambiente,
                        "revision_actual_id": revision_id,
                        "created_at": datetime(2026, 6, 3, 12, 0, 0),
                        "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                    },
                )
            conn.execute(
                Base.metadata.tables["comprobantes"].insert(),
                {
                    "id": 210,
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
                    "empresa_id": 11,
                    "punto_venta_id": 240,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
    finally:
        engine.dispose()


def _windows_access_denied() -> PermissionError:
    error = PermissionError("bloqueo transitorio sintético")
    error.winerror = 5
    return error


def test_publicacion_atomica_acierta_en_el_primer_intento(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    payload = staging / "manifest.json"
    payload.write_bytes(b'{"package_version":4}')
    expected_hash = hashlib.sha256(payload.read_bytes()).hexdigest()
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    real_rename = Path.rename
    calls: list[tuple[Path, Path]] = []
    sleeps: list[float] = []

    def tracked_rename(source: Path, target: Path) -> Path:
        calls.append((source, target))
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", tracked_rename)
    result = vps_migration.publish_staging_directory(
        staging,
        destination,
        ownership,
        platform_name="nt",
        sleep=sleeps.append,
    )

    assert result == destination
    assert calls == [(staging, destination)]
    assert sleeps == []
    assert not os.path.lexists(staging)
    assert hashlib.sha256((destination / "manifest.json").read_bytes()).hexdigest() == (
        expected_hash
    )


def test_publicacion_atomica_reintenta_dos_winerror5_y_conserva_el_arbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    payload = staging / "data.jsonl"
    payload.write_bytes(b'{"id":1}\n')
    expected_hash = hashlib.sha256(payload.read_bytes()).hexdigest()
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    real_rename = Path.rename
    calls: list[tuple[Path, Path]] = []
    sleeps: list[float] = []

    def transient_rename(source: Path, target: Path) -> Path:
        calls.append((source, target))
        if len(calls) <= 2:
            raise _windows_access_denied()
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", transient_rename)
    vps_migration.publish_staging_directory(
        staging,
        destination,
        ownership,
        platform_name="nt",
        sleep=sleeps.append,
    )

    assert calls == [(staging, destination)] * 3
    assert sleeps == [0.05, 0.10]
    assert not os.path.lexists(staging)
    assert hashlib.sha256((destination / "data.jsonl").read_bytes()).hexdigest() == (
        expected_hash
    )


def test_publicacion_atomica_agota_cinco_intentos_y_limpia_solo_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    (staging / "privado.key").write_bytes(b"secreto-sintetico")
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    calls: list[tuple[Path, Path]] = []
    sleeps: list[float] = []

    def denied_rename(source: Path, target: Path) -> Path:
        calls.append((source, target))
        raise _windows_access_denied()

    monkeypatch.setattr(Path, "rename", denied_rename)
    with pytest.raises(vps_migration.MigrationError, match="5 intentos") as caught:
        vps_migration.publish_staging_directory(
            staging,
            destination,
            ownership,
            platform_name="nt",
            sleep=sleeps.append,
        )

    assert isinstance(caught.value.__cause__, PermissionError)
    assert calls == [(staging, destination)] * 5
    assert sleeps == [0.05, 0.10, 0.20, 0.40]
    assert not os.path.lexists(destination)
    vps_migration.cleanup_owned_staging_directory(staging, ownership)
    assert not os.path.lexists(staging)


@pytest.mark.parametrize("appearance", ["initial", "between_attempts"])
def test_publicacion_atomica_preserva_destino_que_ya_existe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    appearance: str,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    (staging / "staging.txt").write_bytes(b"propio")
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    calls = 0
    sleeps: list[float] = []

    def destination_hash() -> str:
        return hashlib.sha256((destination / "ajeno.txt").read_bytes()).hexdigest()

    if appearance == "initial":
        destination.mkdir()
        (destination / "ajeno.txt").write_bytes(b"destino-ajeno")
    expected_hash = destination_hash() if destination.exists() else None

    def racing_rename(source: Path, target: Path) -> Path:
        nonlocal calls, expected_hash
        calls += 1
        destination.mkdir()
        (destination / "ajeno.txt").write_bytes(b"destino-tardio")
        expected_hash = destination_hash()
        raise _windows_access_denied()

    monkeypatch.setattr(Path, "rename", racing_rename)
    with pytest.raises(vps_migration.MigrationError, match="Ya existe"):
        vps_migration.publish_staging_directory(
            staging,
            destination,
            ownership,
            platform_name="nt",
            sleep=sleeps.append,
        )

    assert calls == int(appearance == "between_attempts")
    assert sleeps == []
    assert destination_hash() == expected_hash
    vps_migration.cleanup_owned_staging_directory(staging, ownership)
    assert destination_hash() == expected_hash


@pytest.mark.parametrize(
    ("failure", "platform_name"),
    [
        ("destination", "nt"),
        ("cross_device", "nt"),
        ("other_permission", "nt"),
        ("winerror5_non_windows", "posix"),
    ],
)
def test_publicacion_atomica_no_reintenta_otros_errores_o_plataformas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    platform_name: str,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    calls = 0
    sleeps: list[float] = []

    def fail_rename(source: Path, target: Path) -> Path:
        nonlocal calls
        calls += 1
        if failure == "destination":
            raise FileExistsError("destino apareció en la syscall")
        if failure == "cross_device":
            raise OSError(18, "volumen distinto")
        if failure == "other_permission":
            error = PermissionError("otro permiso")
            error.winerror = 13
            raise error
        raise _windows_access_denied()

    monkeypatch.setattr(Path, "rename", fail_rename)
    expected = (
        PermissionError
        if "permission" in failure or "winerror5" in failure
        else OSError
    )
    with pytest.raises(expected):
        vps_migration.publish_staging_directory(
            staging,
            destination,
            ownership,
            platform_name=platform_name,
            sleep=sleeps.append,
        )

    assert calls == 1
    assert sleeps == []
    assert not os.path.lexists(destination)


@pytest.mark.parametrize("mutation", ["absent", "replaced", "link"])
def test_publicacion_y_limpieza_fallan_cerrado_si_staging_deja_de_ser_propio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    if mutation == "replaced":
        (staging / "propio.txt").write_bytes(b"staging-original")
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    preserved_staging: Path | None = None
    if mutation == "absent":
        staging.rmdir()
    elif mutation == "replaced":
        preserved_staging = output_base / "staging-original"
        staging.rename(preserved_staging)
        staging.mkdir()
        (staging / "ajeno.txt").write_bytes(b"reemplazo")
    else:
        real_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda path: path == staging or real_is_symlink(path),
        )

    with pytest.raises(vps_migration.MigrationError, match="staging"):
        vps_migration.publish_staging_directory(
            staging,
            destination,
            ownership,
            platform_name="nt",
            sleep=lambda _: None,
        )
    if mutation == "absent":
        vps_migration.cleanup_owned_staging_directory(staging, ownership)
        assert not os.path.lexists(staging)
    else:
        with pytest.raises(vps_migration.MigrationError, match="staging|identidad"):
            vps_migration.cleanup_owned_staging_directory(staging, ownership)
        assert os.path.lexists(staging)
        if mutation == "replaced":
            assert preserved_staging is not None
            assert (
                preserved_staging / "propio.txt"
            ).read_bytes() == b"staging-original"
            assert (staging / "ajeno.txt").read_bytes() == b"reemplazo"
    assert not os.path.lexists(destination)


@pytest.mark.parametrize("interrupt_at", ["rename", "sleep"])
def test_publicacion_atomica_no_reintenta_interrupciones(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt_at: str,
) -> None:
    output_base = tmp_path.resolve()
    staging = output_base / "staging"
    destination = output_base / "package"
    staging.mkdir()
    ownership = vps_migration.capture_staging_directory_ownership(staging, output_base)
    calls = 0
    sleeps = 0

    def interrupting_rename(source: Path, target: Path) -> Path:
        nonlocal calls
        calls += 1
        if interrupt_at == "rename":
            raise KeyboardInterrupt
        raise _windows_access_denied()

    def interrupting_sleep(delay: float) -> None:
        nonlocal sleeps
        sleeps += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "rename", interrupting_rename)
    with pytest.raises(KeyboardInterrupt):
        vps_migration.publish_staging_directory(
            staging,
            destination,
            ownership,
            platform_name="nt",
            sleep=interrupting_sleep,
        )

    assert calls == 1
    assert sleeps == int(interrupt_at == "sleep")
    vps_migration.cleanup_owned_staging_directory(staging, ownership)
    assert not os.path.lexists(staging)


def test_export_publica_con_reintento_atomico_y_manifest_verificable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path, certs_dir = _create_source_db(tmp_path)
    real_rename = Path.rename
    real_publish = vps_migration.publish_staging_directory
    calls: list[tuple[Path, Path]] = []
    sleeps: list[float] = []

    def transient_rename(source: Path, target: Path) -> Path:
        calls.append((source, target))
        if len(calls) <= 2:
            raise _windows_access_denied()
        return real_rename(source, target)

    def publish_on_windows(
        staging: Path,
        destination: Path,
        ownership: vps_migration.StagingDirectoryOwnership,
    ) -> Path:
        return real_publish(
            staging,
            destination,
            ownership,
            platform_name="nt",
            sleep=sleeps.append,
        )

    monkeypatch.setattr(Path, "rename", transient_rename)
    monkeypatch.setattr(vps_migration, "publish_staging_directory", publish_on_windows)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)

    assert len(calls) == 3
    assert sleeps == [0.05, 0.10]
    assert len({source for source, _ in calls}) == 1
    assert len({target for _, target in calls}) == 1
    assert not os.path.lexists(calls[0][0])
    assert package == calls[0][1]
    for info in manifest["data_files"].values():
        path = package / info["path"]
        assert path.stat().st_size == info["bytes"]
        assert vps_migration.sha256_file(path) == info["sha256"]


def test_export_informa_fallo_de_publicacion_y_cleanup_incompleto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path, certs_dir = _create_source_db(tmp_path)
    real_publish = vps_migration.publish_staging_directory
    sleeps: list[float] = []

    def denied_rename(source: Path, target: Path) -> Path:
        raise _windows_access_denied()

    def failed_cleanup(path: Path) -> None:
        raise PermissionError("cleanup sintético fallido")

    def publish_on_windows(
        staging: Path,
        destination: Path,
        ownership: vps_migration.StagingDirectoryOwnership,
    ) -> Path:
        return real_publish(
            staging,
            destination,
            ownership,
            platform_name="nt",
            sleep=sleeps.append,
        )

    monkeypatch.setattr(Path, "rename", denied_rename)
    monkeypatch.setattr(vps_migration, "publish_staging_directory", publish_on_windows)
    monkeypatch.setattr(vps_migration.shutil, "rmtree", failed_cleanup)
    with pytest.raises(
        vps_migration.MigrationError, match="limpieza.*incompleta"
    ) as caught:
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=tmp_path / "packages",
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert isinstance(caught.value.__cause__, BaseExceptionGroup)
    failures = caught.value.__cause__.exceptions
    assert any(
        isinstance(failure, vps_migration.MigrationError) for failure in failures
    )
    assert any(isinstance(failure, PermissionError) for failure in failures)
    assert sleeps == [0.05, 0.10, 0.20, 0.40]
    remaining = list((tmp_path / "packages").iterdir())
    assert len(remaining) == 1
    assert remaining[0].name.startswith(".")
    assert remaining[0].name.endswith(".tmp")


@pytest.mark.parametrize(
    ("interruption_type", "exit_code"),
    [(KeyboardInterrupt, None), (SystemExit, 73)],
    ids=["keyboard_interrupt", "system_exit"],
)
def test_export_propaga_interrupcion_de_cleanup_y_preserva_fallo_publicacion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption_type: Any,
    exit_code: int | None,
) -> None:
    db_path, certs_dir = _create_source_db(tmp_path)
    publication_error = vps_migration.MigrationError("publicación sintética fallida")
    cleanup_interruption = (
        interruption_type() if exit_code is None else interruption_type(exit_code)
    )

    def failed_publication(*args: Any, **kwargs: Any) -> Path:
        raise publication_error

    def interrupted_cleanup(path: Path) -> None:
        assert path.name.startswith(".")
        assert path.name.endswith(".tmp")
        raise cleanup_interruption

    monkeypatch.setattr(vps_migration, "publish_staging_directory", failed_publication)
    monkeypatch.setattr(vps_migration.shutil, "rmtree", interrupted_cleanup)

    with pytest.raises(interruption_type) as caught:
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=tmp_path / "packages",
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert caught.value is cleanup_interruption
    assert caught.value.__cause__ is publication_error
    assert any("limpieza" in note for note in caught.value.__notes__)
    if exit_code is not None:
        assert caught.value.code == exit_code


@pytest.mark.parametrize(
    ("cleanup_interruption", "publication_interruption", "exit_code"),
    [
        (KeyboardInterrupt(), SystemExit(41), None),
        (SystemExit(73), KeyboardInterrupt(), 73),
    ],
    ids=["keyboard_interrupt", "system_exit"],
)
def test_export_propaga_interrupcion_mas_reciente_si_ambas_interrumpen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_interruption: BaseException,
    publication_interruption: BaseException,
    exit_code: int | None,
) -> None:
    db_path, certs_dir = _create_source_db(tmp_path)

    def interrupted_publication(*args: Any, **kwargs: Any) -> Path:
        raise publication_interruption

    def interrupted_cleanup(path: Path) -> None:
        assert path.name.startswith(".")
        assert path.name.endswith(".tmp")
        raise cleanup_interruption

    monkeypatch.setattr(
        vps_migration, "publish_staging_directory", interrupted_publication
    )
    monkeypatch.setattr(vps_migration.shutil, "rmtree", interrupted_cleanup)

    with pytest.raises(type(cleanup_interruption)) as caught:
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=tmp_path / "packages",
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert caught.value is cleanup_interruption
    assert caught.value.__cause__ is publication_interruption
    assert any("limpieza" in note for note in caught.value.__notes__)
    if exit_code is not None:
        assert isinstance(caught.value, SystemExit)
        assert caught.value.code == exit_code


def test_export_propaga_interrupcion_y_limpia_staging_propio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path, certs_dir = _create_source_db(tmp_path)

    def interrupt_publication(*args: Any, **kwargs: Any) -> Path:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        vps_migration, "publish_staging_directory", interrupt_publication
    )
    with pytest.raises(KeyboardInterrupt):
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=tmp_path / "packages",
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert list((tmp_path / "packages").iterdir()) == []


def test_exporta_solo_tablas_incluidas_y_excluye_lotes(tmp_path: Path) -> None:
    """El paquete v4 declara toda su partición y omite sólo filas no requeridas."""
    db_path, certs_dir = _create_source_db(tmp_path)

    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )

    manifest = vps_migration.load_and_verify_manifest(package)
    assert set(manifest["included_tables"]) == set(vps_migration_v4.INCLUDED_TABLES)
    assert manifest["data_files"]["lotes_comprobantes"]["rows"] == 0
    assert (package / "data" / "lotes_comprobantes.jsonl").exists()
    assert manifest["data_files"]["comprobantes"]["rows"] == 1
    assert manifest["omitted_counts"]["lotes_comprobantes"] == 1
    assert manifest["safe_omitted"]["omitted_counts"] == manifest["omitted_counts"]
    assert (
        manifest["safe_omitted"]["legacy_preflight"]["excluded_counts"][
            "lotes_comprobantes"
        ]
        == 1
    )
    assert (package / "manifest.json").is_file()
    assert (package / "env.production.required.example").is_file()
    assert not any(path.name.endswith(".tmp") for path in package.parent.iterdir())


def test_export_requiere_confirmacion_explicita_de_fuente_quiescente(
    tmp_path: Path,
) -> None:
    """La afirmación operativa es obligatoria además del lock SQLite."""
    db_path, certs_dir = _create_source_db(tmp_path)
    output_root = tmp_path / "packages"

    with pytest.raises(vps_migration.MigrationError, match="source-quiesced"):
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=output_root,
            target_key_password="clave-destino-larga",
        )

    assert not output_root.exists()


def test_preflight_bloquea_compatibilidad_multiemisor_incoherente(
    tmp_path: Path,
) -> None:
    """El paquete no debe perder una asignación por un singular desactualizado."""
    db_path, certs_dir = _create_source_db(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE usuarios SET empresa_id = NULL WHERE id = 20")

    with pytest.raises(
        vps_migration.MigrationError,
        match="no coincide",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize(
    ("estado", "blocker"),
    [
        ("en_proceso", "operaciones_no_terminales"),
        ("requiere_reconciliacion", "operaciones_no_terminales"),
        ("estado_desconocido", "operaciones_estado_desconocido"),
        ("finalizado", "operaciones_terminales_sin_respuesta"),
    ],
)
def test_preflight_bloquea_operacion_activa_incierta_unknown_o_sin_respuesta(
    tmp_path: Path,
    estado: str,
    blocker: str,
) -> None:
    """Ninguna operación continuable o sin replay durable puede exportarse."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(db_path, estado=estado, response_json=None)

    with pytest.raises(vps_migration.MigrationError, match=blocker):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize(
    "estado",
    ["en_cola", "procesando", "requiere_reconciliacion", "estado_desconocido"],
)
def test_preflight_bloquea_lote_activo_incierto_o_unknown(
    tmp_path: Path,
    estado: str,
) -> None:
    """Un lote omitido no puede conservar trabajo activo o incierto."""
    db_path, certs_dir = _create_source_db(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE lotes_comprobantes SET estado = ? WHERE id = 130",
            (estado,),
        )

    with pytest.raises(
        vps_migration.MigrationError,
        match="lotes_activos_inciertos_o_desconocidos",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize("target", ["grupo", "fila"])
@pytest.mark.parametrize(
    "estado",
    ["reintentando", "requiere_reconciliacion", "estado_desconocido"],
)
def test_preflight_bloquea_grupo_o_fila_activa_incierta_o_unknown(
    tmp_path: Path,
    target: str,
    estado: str,
) -> None:
    """Grupos y filas excluidos deben estar en estados pre-ARCA seguros."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_group_and_row(
        db_path,
        group_state=estado if target == "grupo" else "validado",
        row_state=estado if target == "fila" else "validado",
    )

    expected = (
        "grupos_activos_inciertos_o_desconocidos"
        if target == "grupo"
        else "filas_activas_inciertas_o_desconocidas"
    )
    with pytest.raises(vps_migration.MigrationError, match=expected):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_grupo_y_fila_pre_arca_seguros(tmp_path: Path) -> None:
    """Un grupo validado sin evidencia ARCA puede omitirse de forma auditable."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_group_and_row(db_path)

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["grupos_seguros_omitidos"] == 1
    assert legacy_preflight["filas_omitidas"] == 1


def test_preflight_bloquea_grupo_autorizado_sin_comprobante(
    tmp_path: Path,
) -> None:
    """Una autorización sin comprobante incluido no puede omitirse del paquete."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_group_and_row(
        db_path,
        group_state="autorizado",
        row_state="autorizado",
        authorized_evidence=True,
        include_comprobante=False,
        legacy_snapshot=True,
    )

    with pytest.raises(
        vps_migration.MigrationError,
        match="grupos_evidencia_fiscal_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_grupo_autorizado_con_comprobante_coherente(
    tmp_path: Path,
) -> None:
    """La evidencia autorizada solo es omitible si coincide con el comprobante."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_group_and_row(
        db_path,
        group_state="autorizado",
        row_state="autorizado",
        authorized_evidence=True,
    )

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["grupos_seguros_omitidos"] == 1
    assert legacy_preflight["filas_omitidas"] == 1


def test_preflight_admite_grupo_autorizado_legacy_con_comprobante_coherente(
    tmp_path: Path,
) -> None:
    """Un autorizado pre-b9 deriva el PV desde su comprobante incluido."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_group_and_row(
        db_path,
        group_state="autorizado",
        row_state="autorizado",
        authorized_evidence=True,
        legacy_snapshot=True,
    )

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert result.safe_omitted["legacy_preflight"]["grupos_seguros_omitidos"] == 1


def test_preflight_bloquea_grupo_autorizado_legacy_con_comprobante_cruzado(
    tmp_path: Path,
) -> None:
    """La compatibilidad legacy nunca admite evidencia de otro emisor."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_foreign_comprobante(db_path)
    _insert_group_and_row(
        db_path,
        group_state="autorizado",
        row_state="autorizado",
        authorized_evidence=True,
        legacy_snapshot=True,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE lotes_comprobantes_grupos SET comprobante_id = 210 WHERE id = 160"
        )

    with pytest.raises(
        vps_migration.MigrationError,
        match="grupos_evidencia_fiscal_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_fila_con_estado_distinto_del_grupo(
    tmp_path: Path,
) -> None:
    """Una fila omitida debe conservar el mismo estado fiscal que su grupo."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_group_and_row(
        db_path,
        group_state="validado",
        row_state="cargado",
    )

    with pytest.raises(
        vps_migration.MigrationError,
        match="filas_estado_grupo_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_guarda_terminal_con_intento_canonico(
    tmp_path: Path,
) -> None:
    """Una guarda cerrada pre-ARCA se omite solo con su intento fallido durable."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["intentos_terminales_omitidos"] == 1
    assert legacy_preflight["guardas_terminales_omitidas"] == 1


def test_preflight_omite_rechazo_global_pf19c_con_evidencia_exacta(
    tmp_path: Path,
) -> None:
    """El 10005 individual conserva su intento histórico sólo si es exacto."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_global_rejection(db_path)

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert result.safe_omitted["legacy_preflight"]["intentos_terminales_omitidos"] == 1
    assert result.included_counts["intentos_emision_fiscal"] == 1
    assert result.safe_omitted["omitted_counts"]["intentos_emision_fiscal"] == 0


def test_preflight_omite_rechazo_global_pf19c_batch_con_grafo_exacto(
    tmp_path: Path,
) -> None:
    """El 10005 batch exige replay, lote, grupo e intento del mismo grafo."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_batch_global_rejection(db_path)

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["intentos_terminales_omitidos"] == 1
    assert legacy_preflight["grupos_seguros_omitidos"] == 1
    assert legacy_preflight["operaciones_terminales_preservadas"] == 1


def test_preflight_conserva_rechazo_pf19c_supersedido_por_reintento_exitoso(
    tmp_path: Path,
) -> None:
    """A conserva su replay y B autoriza solo con un grafo terminal posterior."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_batch_success_after_global_rejection(db_path)

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["intentos_terminales_omitidos"] == 2
    assert legacy_preflight["guardas_terminales_omitidas"] == 2
    assert legacy_preflight["grupos_seguros_omitidos"] == 1
    assert legacy_preflight["operaciones_terminales_preservadas"] == 2


def test_paquete_conserva_roles_pf19c_por_operacion_tras_supersesion(
    tmp_path: Path,
) -> None:
    """El manifest atribuye el 10005 solo a A y deja B como éxito terminal."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_batch_success_after_global_rejection(db_path)

    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)

    normalization = manifest["normalizations"]["operaciones_idempotentes.lote_id"]
    assert normalization["pairs"] == []
    operations = _read_package_jsonl_rows(package, manifest, "operaciones_idempotentes")
    assert {
        int(operation["id"]): int(operation["lote_id"]) for operation in operations
    } == {140: 130, 240: 130}
    attempts = _read_package_jsonl_rows(package, manifest, "intentos_emision_fiscal")
    assert {
        (int(attempt["operacion_id"]), attempt["estado"]) for attempt in attempts
    } == {
        (140, "rechazado_arca"),
        (240, "autorizado"),
    }


@pytest.mark.parametrize(
    "mutation",
    ["respuesta", "marker", "owner", "intento", "intento_duplicado"],
)
def test_preflight_bloquea_rechazo_global_pf19c_batch_mutado(
    tmp_path: Path,
    mutation: str,
) -> None:
    """No se omite un batch 10005 si se desliga su evidencia autocontenida."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_batch_global_rejection(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            if mutation in {"respuesta", "marker", "owner"}:
                response = _batch_global_rejection_response()
                if mutation == "respuesta":
                    response["errores_arca"] = []
                elif mutation == "marker":
                    response["lote"]["metadata_json"]["pf19c_rechazo_global"][
                        "grupos_rechazo_ids"
                    ] = [999]
                else:
                    response["lote"]["metadata_json"]["pf19c_rechazo_global"][
                        "operacion_id"
                    ] = 999
                conn.execute(
                    Base.metadata.tables["operaciones_idempotentes"]
                    .update()
                    .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                    .values(response_json=response)
                )
            elif mutation == "intento":
                conn.execute(
                    Base.metadata.tables["intentos_emision_fiscal"]
                    .update()
                    .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                    .values(lote_id=None, grupo_id=None)
                )
            else:
                intento = dict(
                    conn.execute(
                        select(Base.metadata.tables["intentos_emision_fiscal"]).where(
                            Base.metadata.tables["intentos_emision_fiscal"].c.id == 143
                        )
                    )
                    .mappings()
                    .one()
                )
                intento.update(
                    id=144,
                    categoria_error="arca_no_aprobado",
                    errores_arca_json=None,
                )
                conn.execute(
                    Base.metadata.tables["intentos_emision_fiscal"].insert(),
                    intento,
                )
    finally:
        engine.dispose()

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize(
    "mutation",
    ["error_arca", "respuesta", "categoria", "texto_publico"],
)
def test_preflight_bloquea_rechazo_global_pf19c_mutado(
    tmp_path: Path,
    mutation: str,
) -> None:
    """No se omite un 10005 si cambia su evidencia durable o su replay."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_global_rejection(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            if mutation == "error_arca":
                conn.execute(
                    Base.metadata.tables["intentos_emision_fiscal"]
                    .update()
                    .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                    .values(
                        errores_arca_json=[
                            {
                                "codigo": 10005.0,
                                "alcance": "global",
                                "mensaje": "El punto de venta no está dado de alta como RECE en ARCA.",
                            }
                        ]
                    )
                )
            elif mutation == "respuesta":
                response = _individual_global_rejection_response()
                response["errores_arca"] = []
                conn.execute(
                    Base.metadata.tables["operaciones_idempotentes"]
                    .update()
                    .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                    .values(response_json=response)
                )
            elif mutation == "categoria":
                conn.execute(
                    Base.metadata.tables["intentos_emision_fiscal"]
                    .update()
                    .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                    .values(categoria_error="arca_no_aprobado")
                )
            else:
                response = _individual_global_rejection_response()
                response["mensaje"] = "Reintentá inmediatamente"
                response["errores"] = []
                conn.execute(
                    Base.metadata.tables["operaciones_idempotentes"]
                    .update()
                    .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                    .values(response_json=response)
                )
    finally:
        engine.dispose()

    with pytest.raises(
        vps_migration.MigrationError,
        match="rechazo_global_pf19c_incoherentes",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_omite_journal_legacy_pf19_y_declara_target_vacio(
    tmp_path: Path,
) -> None:
    """El journal legacy se cuenta y nunca se serializa hacia el VPS."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_legacy_pf19_journal(db_path)

    result = vps_migration.run_preflight(db_path, certs_dir)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)

    assert (
        result.safe_omitted["legacy_preflight"]["resoluciones_legacy_pf19_omitidas"]
        == 1
    )
    assert manifest["omitted_counts"]["resoluciones_legacy_pf19_journal"] == 1
    assert "resoluciones_legacy_pf19_journal" in manifest["target_empty_tables"]
    assert "resoluciones_legacy_pf19_journal" not in manifest["data_files"]


def test_preflight_omite_journal_legacy_pf19_batch_con_replay_exacto(
    tmp_path: Path,
) -> None:
    """El journal batch solo se omite si intento, grupo, lote y DTO coinciden."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_legacy_pf19_batch_journal(db_path)

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["resoluciones_legacy_pf19_omitidas"] == 1
    assert legacy_preflight["intentos_terminales_omitidos"] == 1
    assert legacy_preflight["grupos_seguros_omitidos"] == 1


def test_preflight_bloquea_journal_legacy_pf19_batch_con_mensaje_mutado(
    tmp_path: Path,
) -> None:
    """Un envelope batch genérico no prueba el cierre legacy auditado."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_legacy_pf19_batch_journal(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            response = {
                "lote": _lote_response_payload(),
                "mensaje": "Resultado batch genérico",
                "en_progreso": False,
                "errores_arca": [],
            }
            response["lote"]["estado"] = "fallido"
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(response_json=response)
            )
            conn.execute(
                Base.metadata.tables["resoluciones_legacy_pf19_journal"]
                .update()
                .where(
                    Base.metadata.tables["resoluciones_legacy_pf19_journal"].c.id == 170
                )
                .values(terminal_response_sha256=_canonical_json_sha256(response))
            )
    finally:
        engine.dispose()

    with pytest.raises(
        vps_migration.MigrationError,
        match="journals_legacy_pf19_incoherentes",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_journal_legacy_pf19_batch_con_dto_coordinado(
    tmp_path: Path,
) -> None:
    """La huella reatestiguada no reemplaza el cruce con el lote fuente exacto."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_legacy_pf19_batch_journal(db_path)
    response = {
        "lote": _lote_response_payload(),
        "mensaje": "Cierre legacy por ausencia de autorización verificada",
        "en_progreso": False,
        "errores_arca": [],
    }
    response["lote"].update(
        {
            "estado": "fallido",
            "grupos_emitidos": 0,
            "grupos_fallidos": 1,
            "total_grupos": 999,
            "mensaje_resumen": response["mensaje"],
        }
    )
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(response_json=response)
            )
            conn.execute(
                Base.metadata.tables["resoluciones_legacy_pf19_journal"]
                .update()
                .where(
                    Base.metadata.tables["resoluciones_legacy_pf19_journal"].c.id == 170
                )
                .values(terminal_response_sha256=_canonical_json_sha256(response))
            )
    finally:
        engine.dispose()

    with pytest.raises(
        vps_migration.MigrationError,
        match="journals_legacy_pf19_incoherentes",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize(
    "mutation",
    ["error_arca", "orphan", "response", "huella"],
)
def test_preflight_bloquea_journal_legacy_pf19_incoherente(
    tmp_path: Path,
    mutation: str,
) -> None:
    """El journal no puede omitir un cierre legacy sin su grafo coherente."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_legacy_pf19_journal(db_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            if mutation == "error_arca":
                conn.execute(
                    Base.metadata.tables["intentos_emision_fiscal"]
                    .update()
                    .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
                    .values(errores_arca_json=[])
                )
            elif mutation == "orphan":
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(
                    Base.metadata.tables["resoluciones_legacy_pf19_journal"]
                    .update()
                    .where(
                        Base.metadata.tables["resoluciones_legacy_pf19_journal"].c.id
                        == 170
                    )
                    .values(intento_id=999)
                )
            elif mutation == "response":
                response = _individual_success_response(
                    exito=False,
                    comprobante_id=None,
                    numero=124,
                    cae=None,
                    cae_vencimiento=None,
                    categoria_error="arca_no_aprobado",
                )
                conn.execute(
                    Base.metadata.tables["operaciones_idempotentes"]
                    .update()
                    .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                    .values(response_json=response)
                )
            else:
                conn.execute(
                    Base.metadata.tables["resoluciones_legacy_pf19_journal"]
                    .update()
                    .where(
                        Base.metadata.tables["resoluciones_legacy_pf19_journal"].c.id
                        == 170
                    )
                    .values(terminal_response_sha256="3" * 64)
                )
    finally:
        engine.dispose()

    with pytest.raises(
        vps_migration.MigrationError,
        match="legacy|referencias inválidas",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_respuesta_negativa_con_intento_autorizado(
    tmp_path: Path,
) -> None:
    """Una respuesta negativa no puede ocultar evidencia ARCA positiva."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _authorize_terminal_guard_context(db_path, publish_success=False)

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_individuales_resultado_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_respuesta_exitosa_moderna_sin_intento_autorizado(
    tmp_path: Path,
) -> None:
    """Un replay moderno exitoso requiere el intento autorizado canónico."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["intentos_emision_fiscal"]
                .delete()
                .where(Base.metadata.tables["intentos_emision_fiscal"].c.id == 143)
            )
            conn.execute(
                Base.metadata.tables["puntos_venta_guardas_emision_rece"]
                .delete()
                .where(
                    Base.metadata.tables["puntos_venta_guardas_emision_rece"].c.id
                    == 142
                )
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(
                    estado="finalizado",
                    response_json=_individual_success_response(),
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_individuales_resultado_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_respuesta_exitosa_con_intento_autorizado(
    tmp_path: Path,
) -> None:
    """Respuesta, comprobante, intento y guarda coherentes preservan el replay."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _authorize_terminal_guard_context(db_path, publish_success=True)

    result = vps_migration.run_preflight(db_path, certs_dir)

    legacy_preflight = result.safe_omitted["legacy_preflight"]
    assert legacy_preflight["operaciones_terminales_preservadas"] == 1
    assert legacy_preflight["intentos_terminales_omitidos"] == 1


def test_preflight_bloquea_exito_moderno_con_intento_legacy_sin_guarda(
    tmp_path: Path,
) -> None:
    """Una asociación PF19B no puede cerrarse con evidencia legacy desacoplada."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _authorize_terminal_guard_context(db_path, publish_success=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""
            UPDATE intentos_emision_fiscal
            SET guarda_rece_id = NULL,
                ambiente = NULL,
                punto_venta_elegibilidad_revision_id = NULL,
                punto_venta_revision_fiscal = NULL
            WHERE id = 143
            """)
        conn.execute("DELETE FROM puntos_venta_guardas_emision_rece WHERE id = 142")

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_individuales_resultado_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_replay_legacy_exitoso_sin_intentos(
    tmp_path: Path,
) -> None:
    """Un terminal pre-PF19B conserva su replay durable sin inventar evidencia."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json=_individual_success_response(),
        tipo_operacion="emitir_comprobante",
        lote_id=None,
    )

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert (
        result.safe_omitted["legacy_preflight"]["operaciones_terminales_preservadas"]
        == 1
    )


def test_preflight_bloquea_guarda_terminal_huerfana(tmp_path: Path) -> None:
    """Una guarda cerrada sin intentos conserva evidencia fiscal incoherente."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=False)

    with pytest.raises(
        vps_migration.MigrationError,
        match="guardas_huerfanas_sin_intentos",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_intento_y_guarda_activos(tmp_path: Path) -> None:
    """Una guarda pre-ARCA y su reserva activa impiden omitir evidencia fiscal."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            UPDATE puntos_venta_guardas_emision_rece
            SET fase = 'pre_arca', cerrada_en = NULL
            WHERE id = 142
            """)
        conn.execute(
            "UPDATE intentos_emision_fiscal SET estado = 'en_proceso' WHERE id = 143"
        )

    with pytest.raises(vps_migration.MigrationError) as exc:
        vps_migration.run_preflight(db_path, certs_dir)

    assert "intentos_no_terminales" in str(exc.value)
    assert "guardas_no_terminales" in str(exc.value)


def test_preflight_bloquea_digest_rece_terminal_adulterado(tmp_path: Path) -> None:
    """Una asociación válida no autoriza un digest distinto al snapshot histórico."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE operaciones_idempotentes
            SET rece_snapshot_hash = ?
            WHERE id = 140
            """,
            ("f" * 64,),
        )

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_digest_rece_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_emision_individual_con_dos_asociaciones(
    tmp_path: Path,
) -> None:
    """Una emisión individual moderna captura exactamente un contexto RECE."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    contexts = [
        {
            "empresa_id": 10,
            "punto_venta_id": point_id,
            "punto_venta_numero": point_number,
            "ambiente": "produccion",
            "elegibilidad_revision_id": revision_id,
            "punto_venta_revision_fiscal": 1,
        }
        for point_id, point_number, revision_id in (
            (40, 6, 45),
            (240, 8, 245),
        )
    ]
    digest = hashlib.sha256(
        json.dumps(
            {"version": 1, "contextos": contexts},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["puntos_venta"].insert(),
                {
                    "id": 240,
                    "numero": 8,
                    "nombre": "Segundo Web Services",
                    "es_webservice": True,
                    "bloqueado": False,
                    "activo": True,
                    "revision_fiscal": 1,
                    "empresa_id": 10,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            for revision_id, ambiente, revision, estado in (
                (241, "homologacion", 1, "no_verificado"),
                (242, "produccion", 1, "no_verificado"),
                (245, "produccion", 2, "verificado_rece"),
            ):
                values: dict[str, Any] = {
                    "id": revision_id,
                    "empresa_id": 10,
                    "punto_venta_id": 240,
                    "ambiente": ambiente,
                    "revision": revision,
                    "estado": estado,
                    "fuente": (
                        "constancia_arca_atestada"
                        if estado == "verificado_rece"
                        else "migracion_legacy"
                    ),
                    "evidencia_tipo": (
                        "rece_aplicativo_web_services_v1"
                        if estado == "verificado_rece"
                        else "sin_evidencia"
                    ),
                    "punto_venta_numero_snapshot": 8,
                    "punto_revision_fiscal": 1,
                    "observado_en": datetime(2026, 6, 3, 12, 0, 0),
                    "actor_usuario_id_snapshot": 20,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                }
                if estado == "verificado_rece":
                    values.update(
                        {
                            "evidencia_sha256": "f" * 64,
                            "clasificador_version": "rece-v1",
                            "empresa_cuit_snapshot": "20123456789",
                            "documento_emitido_en": date(2026, 6, 3),
                            "vigente_hasta": date(2027, 6, 3),
                            "verificado_en": datetime(2026, 6, 3, 12, 0, 0),
                            "creado_por_usuario_id": 20,
                        }
                    )
                conn.execute(
                    Base.metadata.tables[
                        "puntos_venta_elegibilidad_rece_revisiones"
                    ].insert(),
                    values,
                )
            for head_id, ambiente, revision_id in (
                (243, "homologacion", 241),
                (244, "produccion", 245),
            ):
                conn.execute(
                    Base.metadata.tables[
                        "puntos_venta_elegibilidad_rece_actual"
                    ].insert(),
                    {
                        "id": head_id,
                        "empresa_id": 10,
                        "punto_venta_id": 240,
                        "ambiente": ambiente,
                        "revision_actual_id": revision_id,
                        "created_at": datetime(2026, 6, 3, 12, 0, 0),
                        "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                    },
                )
            conn.execute(
                Base.metadata.tables[
                    "operaciones_idempotentes_elegibilidad_rece"
                ].insert(),
                {
                    "id": 147,
                    "operacion_id": 140,
                    "empresa_id": 10,
                    "punto_venta_id": 240,
                    "ambiente": "produccion",
                    "elegibilidad_revision_id": 245,
                    "punto_venta_revision_fiscal": 1,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["operaciones_idempotentes"]
                .update()
                .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(rece_snapshot_hash=digest)
            )
    finally:
        engine.dispose()

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_individuales_asociacion_incoherente",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_head_fiscal_historica(tmp_path: Path) -> None:
    """Una cabeza histórica válida puede quedar detrás de la revisión del punto."""
    db_path, certs_dir = _create_source_db(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE puntos_venta SET revision_fiscal = 2 WHERE id = 40")

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert result.included_counts["puntos_venta_elegibilidad_rece_actual"] == 2


def test_preflight_digesta_numero_historico_de_la_revision(tmp_path: Path) -> None:
    """Renumerar luego del cierre no invalida un replay exitoso histórico."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _authorize_terminal_guard_context(db_path, publish_success=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables["puntos_venta"]
                .update()
                .where(Base.metadata.tables["puntos_venta"].c.id == 40)
                .values(numero=7, revision_fiscal=2)
            )
            for revision_id, ambiente, revision in (
                (46, "homologacion", 2),
                (47, "produccion", 3),
            ):
                conn.execute(
                    Base.metadata.tables[
                        "puntos_venta_elegibilidad_rece_revisiones"
                    ].insert(),
                    {
                        "id": revision_id,
                        "empresa_id": 10,
                        "punto_venta_id": 40,
                        "ambiente": ambiente,
                        "revision": revision,
                        "estado": "no_verificado",
                        "fuente": "edicion",
                        "evidencia_tipo": "sin_evidencia",
                        "punto_venta_numero_snapshot": 7,
                        "punto_revision_fiscal": 2,
                        "observado_en": datetime(2026, 6, 3, 12, 2, 0),
                        "actor_usuario_id_snapshot": 20,
                        "created_at": datetime(2026, 6, 3, 12, 2, 0),
                    },
                )
            conn.execute(
                Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"].c.id
                    == 43
                )
                .values(revision_actual_id=46)
            )
            conn.execute(
                Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"].c.id
                    == 44
                )
                .values(revision_actual_id=47)
            )
    finally:
        engine.dispose()

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert result.safe_omitted["legacy_preflight"]["asociaciones_rece_preservadas"] == 1


def test_preflight_bloquea_hueco_en_ledger_append_only(tmp_path: Path) -> None:
    """Una cabeza máxima no legitima una secuencia RECE truncada 1,3."""
    db_path, certs_dir = _create_source_db(tmp_path)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                Base.metadata.tables[
                    "puntos_venta_elegibilidad_rece_revisiones"
                ].insert(),
                {
                    "id": 45,
                    "empresa_id": 10,
                    "punto_venta_id": 40,
                    "ambiente": "produccion",
                    "revision": 3,
                    "estado": "no_verificado",
                    "fuente": "edicion",
                    "evidencia_tipo": "sin_evidencia",
                    "punto_revision_fiscal": 1,
                    "observado_en": datetime(2026, 6, 3, 12, 0, 0),
                    "actor_usuario_id_snapshot": 20,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
            conn.execute(
                Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"]
                .update()
                .where(
                    Base.metadata.tables["puntos_venta_elegibilidad_rece_actual"].c.id
                    == 44
                )
                .values(revision_actual_id=45)
            )
    finally:
        engine.dispose()

    with pytest.raises(vps_migration.MigrationError, match="hueco"):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("fecha", "31/02/2026"),
        ("numero", "no-es-numero"),
        ("total", "no-es-total"),
    ],
)
def test_preflight_bloquea_dto_individual_terminal_invalido(
    tmp_path: Path,
    field_name: str,
    invalid_value: Any,
) -> None:
    """El replay individual debe validar el DTO completo del endpoint."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json=_individual_success_response(**{field_name: invalid_value}),
        tipo_operacion="emitir_comprobante",
        lote_id=None,
    )

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_terminales_respuesta_invalida",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


@pytest.mark.parametrize(
    "overrides",
    [
        {"comprobante_id": 999},
        {"cae": "99999999999999"},
        {"numero": 999},
        {"fecha": "2026-06-04"},
        {"total": "999.00"},
    ],
)
def test_preflight_bloquea_replay_individual_cruzado_con_comprobante(
    tmp_path: Path,
    overrides: dict[str, Any],
) -> None:
    """Un DTO válido no alcanza si contradice el comprobante fiscal incluido."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json=_individual_success_response(**overrides),
        tipo_operacion="emitir_comprobante",
        lote_id=None,
    )

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_exitosas_sin_comprobante",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_replay_individual_de_otro_emisor(tmp_path: Path) -> None:
    """La respuesta no puede apuntar a un comprobante válido de otro emisor."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_foreign_comprobante(db_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json=_individual_success_response(comprobante_id=210),
        tipo_operacion="emitir_comprobante",
        lote_id=None,
    )

    with pytest.raises(
        vps_migration.MigrationError,
        match="operaciones_exitosas_sin_comprobante",
    ):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_bloquea_replay_lote_incompleto(tmp_path: Path) -> None:
    """El replay de lote debe conservar el DTO completo del endpoint."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json={
            "lote": {"id": 130},
            "mensaje": "incompleta",
            "en_progreso": False,
        },
    )

    with pytest.raises(vps_migration.MigrationError, match="operaciones_"):
        vps_migration.run_preflight(db_path, certs_dir)


def test_preflight_admite_replay_lote_tras_cierre_posterior(tmp_path: Path) -> None:
    """El snapshot terminal sigue válido si el lote luego cambia de estado seguro."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json={
            "lote": {**_lote_response_payload(), "grupos_emitidos": 0},
            "mensaje": "Snapshot terminal histórico",
            "en_progreso": False,
        },
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            UPDATE lotes_comprobantes
            SET estado = 'cerrado_reconciliado',
                grupos_emitidos = 1,
                updated_at = '2026-06-04 12:00:00'
            WHERE id = 130
            """)

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert (
        result.safe_omitted["legacy_preflight"]["operaciones_terminales_preservadas"]
        == 1
    )


def test_preflight_admite_error_terminal_lote_sin_mensaje(tmp_path: Path) -> None:
    """El consumer reproduce un error durable por categoría aunque no tenga mensaje."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="fallido_verificado",
        response_json={"categoria_error": "lote_no_procesable"},
    )

    result = vps_migration.run_preflight(db_path, certs_dir)

    assert (
        result.safe_omitted["legacy_preflight"]["operaciones_terminales_preservadas"]
        == 1
    )


def test_export_normaliza_lote_operacion_sin_mutar_fuente(tmp_path: Path) -> None:
    """El paquete desacopla el lote omitido y atestigua el par original."""
    db_path, certs_dir = _create_source_db(tmp_path)
    response = {
        "lote": _lote_response_payload(),
        "mensaje": "Lote procesado",
        "en_progreso": False,
    }
    _insert_operation(db_path, estado="finalizado", response_json=response)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        source_row = dict(
            conn.execute(
                "SELECT * FROM operaciones_idempotentes WHERE id = 140"
            ).fetchone()
        )

    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    exported_rows = [
        json.loads(line)
        for line in (package / "data" / "operaciones_idempotentes.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]

    assert len(exported_rows) == 1
    assert exported_rows[0]["lote_id"] is None
    for key, value in source_row.items():
        if key != "lote_id":
            assert exported_rows[0][key] == value
    pairs = [
        {
            "operacion_id": 140,
            "lote_id": 130,
            "grupo_ids": [],
            "grupos_rechazo_ids": [],
            "grupos_no_enviados_ids": [],
        }
    ]
    canonical = json.dumps(
        pairs,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    normalization = manifest["normalizations"]["operaciones_idempotentes.lote_id"]
    assert normalization == {
        "rule": vps_migration_v4.OPERATION_LOTE_NORMALIZATION_RULE,
        "rows": 1,
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "pairs": pairs,
    }
    assert (
        manifest["safe_omitted"]["legacy_preflight"]["operaciones_lote_normalizado"]
        == 1
    )
    with sqlite3.connect(db_path) as conn:
        assert (
            conn.execute(
                "SELECT lote_id FROM operaciones_idempotentes WHERE id = 140"
            ).fetchone()[0]
            == 130
        )


def test_export_usa_una_conexion_y_bloquea_writer_hasta_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight y JSONL comparten snapshot; otro writer espera hasta el cierre."""
    db_path, certs_dir = _create_source_db(tmp_path)
    original_connect = vps_migration.connect_sqlite_export_snapshot
    original_preflight = vps_migration.run_preflight_on_connection
    original_read = vps_migration.read_table_rows
    connection_ids: set[int] = set()
    statements: list[str] = []
    writer_attempted = False

    def connect_spy(path: Path) -> sqlite3.Connection:
        conn = original_connect(path)
        connection_ids.add(id(conn))
        conn.set_trace_callback(statements.append)
        return conn

    def preflight_spy(conn: sqlite3.Connection, **kwargs: Any) -> Any:
        connection_ids.add(id(conn))
        return original_preflight(conn, **kwargs)

    def read_spy(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
        nonlocal writer_attempted
        connection_ids.add(id(conn))
        if not writer_attempted:
            writer_attempted = True
            writer = sqlite3.connect(db_path, timeout=0, isolation_level=None)
            try:
                with pytest.raises(sqlite3.OperationalError):
                    writer.execute("BEGIN IMMEDIATE")
            finally:
                writer.close()
        return original_read(conn, table_name)

    monkeypatch.setattr(
        vps_migration,
        "connect_sqlite_export_snapshot",
        connect_spy,
    )
    monkeypatch.setattr(vps_migration, "run_preflight_on_connection", preflight_spy)
    monkeypatch.setattr(vps_migration, "read_table_rows", read_spy)

    vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )

    assert writer_attempted
    assert len(connection_ids) == 1
    assert not any(
        statement.strip().upper().startswith("COMMIT") for statement in statements
    )
    writer = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE puntos_venta SET nombre = ? WHERE id = 40",
            ("Writer posterior",),
        )
        writer.rollback()
    finally:
        writer.close()


@pytest.mark.parametrize("failure_point", ["cert_hash", "env", "manifest"])
def test_export_fallido_no_publica_paquete_parcial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    """Todo fallo tardío elimina el staging y deja ausente el paquete final."""
    db_path, certs_dir = _create_source_db(tmp_path)
    output_root = tmp_path / "packages"
    original_sha = vps_migration.sha256_file

    if failure_point == "cert_hash":

        def fail_cert_hash(path: Path) -> str:
            if Path(path).parent.name == "certs":
                raise vps_migration.MigrationError("fallo hash certificado")
            return original_sha(path)

        monkeypatch.setattr(vps_migration, "sha256_file", fail_cert_hash)
    elif failure_point == "env":
        monkeypatch.setattr(
            vps_migration,
            "write_env_template",
            lambda path: (_ for _ in ()).throw(
                vps_migration.MigrationError("fallo plantilla")
            ),
        )
    else:
        monkeypatch.setattr(
            vps_migration,
            "write_json",
            lambda path, payload: (_ for _ in ()).throw(
                vps_migration.MigrationError("fallo manifest")
            ),
        )

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=output_root,
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert output_root.is_dir()
    assert list(output_root.iterdir()) == []


def test_export_interrumpido_limpia_staging_con_material_sensible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KeyboardInterrupt tampoco puede dejar certificados o claves en staging."""
    db_path, certs_dir = _create_source_db(tmp_path)
    output_root = tmp_path / "packages"

    def interrupt_env(path: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(vps_migration, "write_env_template", interrupt_env)

    with pytest.raises(KeyboardInterrupt):
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=output_root,
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert output_root.is_dir()
    assert list(output_root.iterdir()) == []


def test_export_bloquea_colision_de_basename_entre_certificados_activos(
    tmp_path: Path,
) -> None:
    """Dos rutas privadas distintas no pueden aplanarse al mismo nombre destino."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_foreign_comprobante(db_path)
    cert_a = certs_dir / "a"
    cert_b = certs_dir / "b"
    cert_a.mkdir()
    cert_b.mkdir()
    _write_certificate_pair(
        cert_a / "cert.crt",
        cert_a / "a1.key",
        cuit="20123456789",
    )
    _write_certificate_pair(
        cert_b / "cert.crt",
        cert_b / "b1.key",
        cuit="20999999991",
    )
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                Base.metadata.tables["certificados"]
                .update()
                .where(Base.metadata.tables["certificados"].c.id == 50)
                .values(archivo_crt="a/cert.crt", archivo_key="a/a1.key")
            )
            conn.execute(
                Base.metadata.tables["certificados"].insert(),
                {
                    "id": 51,
                    "nombre": "Segundo certificado productivo",
                    "cuit": "20999999991",
                    "fecha_emision": _CERT_TEST_NOT_BEFORE.date(),
                    "fecha_vencimiento": _CERT_TEST_NOT_AFTER.date(),
                    "archivo_crt": "b/cert.crt",
                    "archivo_key": "b/b1.key",
                    "activo": True,
                    "ambiente": "produccion",
                    "empresa_id": 11,
                    "created_at": datetime(2026, 6, 3, 12, 0, 0),
                    "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                },
            )
    finally:
        engine.dispose()
    output_root = tmp_path / "packages"

    with pytest.raises(vps_migration.MigrationError, match="colisionan"):
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=output_root,
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert output_root.is_dir()
    assert list(output_root.iterdir()) == []


@pytest.mark.parametrize(
    "corruption",
    [
        "crt_invalido",
        "par_cruzado",
        "vencido",
        "cuit_cruzado",
        "metadata_fechas",
    ],
)
def test_export_bloquea_certificado_activo_criptograficamente_invalido(
    tmp_path: Path,
    corruption: str,
) -> None:
    """El paquete nunca publica un par activo inválido, cruzado o vencido."""
    db_path, certs_dir = _create_source_db(tmp_path)
    cert_path = next(certs_dir.glob("*.crt"))
    key_path = next(certs_dir.glob("*.key"))
    if corruption == "crt_invalido":
        cert_path.write_bytes(b"no es un certificado X.509")
    elif corruption == "par_cruzado":
        _write_private_key(key_path)
    elif corruption == "vencido":
        _write_certificate_pair(
            cert_path,
            key_path,
            cuit="20123456789",
            not_before=datetime(2020, 1, 1),
            not_after=datetime(2021, 1, 1),
        )
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                UPDATE certificados
                SET fecha_emision = '2020-01-01',
                    fecha_vencimiento = '2021-01-01'
                WHERE id = 50
                """)
    elif corruption == "cuit_cruzado":
        _write_certificate_pair(
            cert_path,
            key_path,
            cuit="20999999991",
        )
    else:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE certificados
                SET fecha_vencimiento = ?
                WHERE id = 50
                """,
                ((_CERT_TEST_NOT_AFTER + timedelta(days=1)).date().isoformat(),),
            )
    output_root = tmp_path / "packages"

    with pytest.raises(
        vps_migration.MigrationError,
        match="validación criptográfica",
    ):
        vps_migration.export_package(
            source_db=db_path,
            certs_dir=certs_dir,
            output_root=output_root,
            target_key_password="clave-destino-larga",
            source_quiesced=True,
        )

    assert output_root.is_dir()
    assert list(output_root.iterdir()) == []


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
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    package_rows = {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in vps_migration.INCLUDED_TABLES
    }

    vps_migration.verify_package_certificates(
        package,
        manifest,
        "clave-destino-larga",
        package_rows,
    )
    with pytest.raises(vps_migration.MigrationError):
        vps_migration.verify_package_certificates(
            package,
            manifest,
            "otra-clave",
            package_rows,
        )


def _reattest_corrupted_certificate_material(
    package: Path,
    manifest: dict[str, Any],
    corruption: str,
) -> None:
    """Adultera un miembro criptográfico y actualiza su atestación de transporte."""
    cert_rows_path = package / manifest["data_files"]["certificados"]["path"]
    cert_rows = [
        json.loads(line)
        for line in cert_rows_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    active = next(row for row in cert_rows if row["activo"] == 1)
    crt_name = active["archivo_crt"]
    key_name = active["archivo_key"]
    crt_path = package / manifest["certificate_files"][crt_name]["path"]
    key_path = package / manifest["certificate_files"][key_name]["path"]

    if corruption == "key_plaintext":
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(),
            password=b"clave-destino-larga",
        )
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        changed_name = key_name
    elif corruption == "key_crossed":
        foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_path.write_bytes(
            foreign_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    b"clave-destino-larga"
                ),
            )
        )
        changed_name = key_name
    else:
        foreign_crt = package / "certs" / "foreign.crt"
        foreign_key = package / "certs" / "foreign.key"
        _write_certificate_pair(
            foreign_crt,
            foreign_key,
            cuit=str(active["cuit"]),
        )
        crt_path.write_bytes(foreign_crt.read_bytes())
        foreign_crt.unlink()
        foreign_key.unlink()
        changed_name = crt_name

    changed_path = package / manifest["certificate_files"][changed_name]["path"]
    changed_info = manifest["certificate_files"][changed_name]
    changed_info["bytes"] = changed_path.stat().st_size
    changed_info["sha256"] = vps_migration.sha256_file(changed_path)
    (package / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "corruption",
    ["key_plaintext", "key_crossed", "crt_crossed"],
)
def test_import_rechaza_par_certificado_reatestiguado_antes_de_tocar_destino(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    """Hashes recalculados no autorizan una clave en claro ni un par cruzado."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    _reattest_corrupted_certificate_material(package, manifest, corruption)
    verified_manifest = vps_migration.load_and_verify_manifest(package)
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    touched: list[str] = []

    monkeypatch.setattr(
        vps_migration,
        "create_postgres_engine",
        lambda url: touched.append("db"),
    )
    monkeypatch.setattr(
        vps_migration,
        "plan_certificate_restore",
        lambda *args: touched.append("certs"),
    )

    with pytest.raises(vps_migration.MigrationError, match="criptográfica estricta"):
        vps_migration.import_package(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
            target_certs_dir=tmp_path / "target-certs",
        )

    assert verified_manifest["certificate_files"] == manifest["certificate_files"]
    assert touched == []
    assert not (tmp_path / "target-certs").exists()


def test_verificacion_restaurada_repite_correspondencia_crt_key(
    tmp_path: Path,
) -> None:
    """El postflight no acepta una clave cruzada aunque su hash sea reatestiguado."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    package_rows = {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in vps_migration.INCLUDED_TABLES
    }
    target_dir = tmp_path / "target-certs"
    vps_migration.restore_certificate_files(package, manifest, target_dir)
    vps_migration.verify_restored_certificate_files(
        target_dir,
        manifest,
        "clave-destino-larga",
        package_rows,
    )

    active = next(row for row in package_rows["certificados"] if row["activo"])
    key_name = str(active["archivo_key"])
    target_key = target_dir / key_name
    foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    target_key.write_bytes(
        foreign_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                b"clave-destino-larga"
            ),
        )
    )
    manifest["certificate_files"][key_name]["sha256"] = vps_migration.sha256_file(
        target_key
    )

    with pytest.raises(vps_migration.MigrationError, match="criptográfica estricta"):
        vps_migration.verify_restored_certificate_files(
            target_dir,
            manifest,
            "clave-destino-larga",
            package_rows,
        )


def test_rechaza_nombres_de_certificados_con_path_traversal(tmp_path: Path) -> None:
    """El importador no debe aceptar destinos de certificados fuera de CERTS_PATH."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filename, info = next(iter(manifest["certificate_files"].items()))
    manifest["certificate_files"] = {f"../{filename}": info}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="Nombre de certificado"):
        vps_migration.load_and_verify_manifest(package)


def _read_package_jsonl_rows(
    package: Path,
    manifest: dict[str, Any],
    table_name: str,
) -> list[dict[str, Any]]:
    """Lee una tabla JSONL ya exportada sin aplicar conversiones de importación."""
    path = package / manifest["data_files"][table_name]["path"]
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _rewrite_package_jsonl_rows(
    package: Path,
    manifest: dict[str, Any],
    table_name: str,
    rows: list[dict[str, Any]],
) -> None:
    """Reescribe JSONL canónico y actualiza su atestación de archivo/conteo."""
    path = package / manifest["data_files"][table_name]["path"]
    vps_migration.write_jsonl(path, rows)
    info = manifest["data_files"][table_name]
    info["rows"] = len(rows)
    info["bytes"] = path.stat().st_size
    info["sha256"] = vps_migration.sha256_file(path)
    manifest["included_counts"][table_name] = len(rows)


def _rebuild_manifest_idempotency_barrier(
    package: Path,
    manifest: dict[str, Any],
) -> None:
    """Recalcula la barrera para aislar validaciones semánticas adversariales."""
    if manifest["package_version"] == vps_migration_v4.PACKAGE_VERSION:
        rows = {
            table: _read_package_jsonl_rows(package, manifest, table)
            for table in vps_migration_v4.INCLUDED_TABLES
        }
        manifest["idempotency_barrier"] = vps_migration.build_v4_idempotency_barrier(
            source_barrier=manifest["source_barrier"],
            normalization=manifest["normalizations"][
                vps_migration_v4.OPERATION_LOTE_NORMALIZATION_KEY
            ],
            closure=manifest["closure"],
            rows=rows,
        )
        return

    manifest["idempotency_barrier"] = vps_migration.build_idempotency_barrier(
        source_barrier=manifest["source_barrier"],
        normalization=manifest["normalizations"][
            vps_migration.OPERATION_LOTE_NORMALIZATION_KEY
        ],
        operation_rows=_read_package_jsonl_rows(
            package,
            manifest,
            "operaciones_idempotentes",
        ),
        association_rows=_read_package_jsonl_rows(
            package,
            manifest,
            "operaciones_idempotentes_elegibilidad_rece",
        ),
    )


def test_barrera_idempotente_canoniza_response_sqlite_y_postgresql() -> None:
    """String JSON SQLite y objeto JSON PostgreSQL producen la misma autoridad."""
    response = {
        "exito": False,
        "mensaje": "Resultado terminal sintético",
        "errores": ["Sin CAE"],
    }
    operation = {
        "id": 140,
        "empresa_id": 10,
        "idempotency_key": "vps-canonical-json",
        "tipo_operacion": "emitir_comprobante",
        "payload_hash": "a" * 64,
        "estado": "fallido_verificado",
        "response_json": response,
        "rece_snapshot_hash": None,
        "lote_id": None,
    }
    _, normalization = vps_migration.normalize_operation_rows([operation])
    kwargs = {
        "source_barrier": {
            "source_quiesced": True,
            "sqlite_transaction": "BEGIN IMMEDIATE",
            "data_version": 1,
        },
        "normalization": normalization,
        "association_rows": [],
    }

    from_postgresql = vps_migration.build_idempotency_barrier(
        operation_rows=[operation],
        **kwargs,
    )
    from_sqlite = vps_migration.build_idempotency_barrier(
        operation_rows=[
            {
                **operation,
                "response_json": json.dumps(response, ensure_ascii=False),
            }
        ],
        **kwargs,
    )

    assert from_sqlite == from_postgresql
    with pytest.raises(vps_migration.MigrationError, match="clave duplicada"):
        vps_migration.build_idempotency_barrier(
            operation_rows=[
                {
                    **operation,
                    "response_json": '{"exito":false,"exito":true}',
                }
            ],
            **kwargs,
        )


def _load_package_into_sqlite_target(
    package: Path,
    manifest: dict[str, Any],
) -> tuple[Any, dict[str, list[dict[str, Any]]]]:
    """Carga el snapshot convertido en una transacción SQLite de prueba B2."""
    contract = vps_migration.select_import_contract(manifest)
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    package_rows = {
        table_name: vps_migration.read_package_rows(
            package,
            manifest,
            table_name,
        )
        for table_name in contract.included_tables
    }
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": manifest["alembic_version"]},
        )
        for table_name in contract.insert_order:
            rows = package_rows[table_name]
            deferred = contract.deferred_columns.get(table_name, ())
            if deferred:
                rows = [
                    {**row, **{column_name: None for column_name in deferred}}
                    for row in rows
                ]
            vps_migration.insert_rows(
                conn,
                table_name,
                rows,
            )
        if contract.package_version == vps_migration_v4.PACKAGE_VERSION:
            vps_migration.restore_deferred_columns(conn, package_rows, contract)
        conn.execute(
            Base.metadata.tables["lotes_duplicados_coordinacion"].insert(),
            vps_migration_v3.coordinator_plan(package_rows["empresas"]),
        )
    return engine, package_rows


def test_restore_deferred_columns_preserva_aristas_y_updated_at(
    tmp_path: Path,
) -> None:
    """Restaurar FKs cíclicas no debe inventar nuevas marcas temporales."""
    package, _, _ = _build_v4_package(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    engine, package_rows = _load_package_into_sqlite_target(package, manifest)
    try:
        with engine.connect() as conn:
            actual_operations = {
                int(row["id"]): row
                for row in vps_migration.read_database_rows(
                    conn, "operaciones_idempotentes"
                )
            }
            actual_groups = {
                int(row["id"]): row
                for row in vps_migration.read_database_rows(
                    conn, "lotes_comprobantes_grupos"
                )
            }
        expected_operations = {
            int(row["id"]): row for row in package_rows["operaciones_idempotentes"]
        }
        expected_groups = {
            int(row["id"]): row for row in package_rows["lotes_comprobantes_grupos"]
        }

        for operation_id in (200, 201):
            assert actual_operations[operation_id]["operacion_raiz_id"] == 200
            assert actual_operations[operation_id]["duplicados_generacion_id"] == (
                301 if operation_id == 200 else 302
            )
            assert actual_operations[operation_id]["updated_at"] == (
                expected_operations[operation_id]["updated_at"]
            )
        assert actual_groups[101]["duplicados_reserva_operacion_id"] == 200
        assert actual_groups[101]["updated_at"] == expected_groups[101]["updated_at"]
    finally:
        engine.dispose()


def test_manifest_v4_rechaza_clave_top_level_extra(tmp_path: Path) -> None:
    """El loader v3 no admite extensiones de shape implícitas o desconocidas."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["extension_no_soportada"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="manifest"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "mutation",
    [
        "top_level_faltante",
        "version",
        "version_float",
        "scope",
        "head",
        "created_at",
        "created_at_offset",
        "included_order",
        "excluded_order",
        "target_order",
        "required_env_order",
        "notes",
        "included_count",
        "excluded_count",
        "safe_omitted_count",
        "active_certificates",
        "data_files_key",
        "data_path",
        "data_rows",
        "data_bytes",
        "data_sha",
        "normalization_rule",
        "normalization_rows",
        "normalization_sha",
        "normalization_pairs",
        "source_quiesced",
        "source_transaction",
        "barrier_rows",
        "barrier_rows_float",
        "barrier_version_float",
        "barrier_algorithm",
        "barrier_sha",
        "env_path",
        "env_bytes",
        "env_sha",
        "certificate_casefold",
    ],
)
def test_manifest_v3_rechaza_mutaciones_de_shape_y_atestaciones(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Cada campo v3 es contractual y se valida contra datos reales/canónicos."""
    package = _build_historical_v3_package(tmp_path)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "top_level_faltante":
        manifest.pop("notes")
    elif mutation == "version":
        manifest["package_version"] = 1
    elif mutation == "version_float":
        manifest["package_version"] = 3.0
    elif mutation == "scope":
        manifest["scope"] = "otro_scope"
    elif mutation == "head":
        manifest["alembic_version"] = "head-inexistente"
    elif mutation == "created_at":
        manifest["created_at"] = "sin-fecha"
    elif mutation == "created_at_offset":
        manifest["created_at"] = "2026-08-09T12:00:00-03:00"
    elif mutation == "included_order":
        manifest["included_tables"] = list(reversed(manifest["included_tables"]))
    elif mutation == "excluded_order":
        manifest["excluded_tables"] = list(reversed(manifest["excluded_tables"]))
    elif mutation == "target_order":
        manifest["target_empty_tables"] = list(
            reversed(manifest["target_empty_tables"])
        )
    elif mutation == "required_env_order":
        manifest["required_env_keys"] = list(reversed(manifest["required_env_keys"]))
    elif mutation == "notes":
        manifest["notes"] = ["nota no contractual"]
    elif mutation == "included_count":
        manifest["included_counts"]["empresas"] += 1
    elif mutation == "excluded_count":
        manifest["excluded_counts"]["lotes_comprobantes"] += 1
    elif mutation == "safe_omitted_count":
        manifest["safe_omitted"]["lotes_seguros_omitidos"] += 1
    elif mutation == "active_certificates":
        manifest["active_certificates"] += 1
    elif mutation == "data_files_key":
        manifest["data_files"]["tabla_extra"] = dict(manifest["data_files"]["empresas"])
    elif mutation == "data_path":
        manifest["data_files"]["empresas"]["path"] = "data/../empresas.jsonl"
    elif mutation == "data_rows":
        manifest["data_files"]["empresas"]["rows"] += 1
    elif mutation == "data_bytes":
        manifest["data_files"]["empresas"]["bytes"] += 1
    elif mutation == "data_sha":
        manifest["data_files"]["empresas"]["sha256"] = "0" * 64
    elif mutation == "normalization_rule":
        manifest["normalizations"][vps_migration.OPERATION_LOTE_NORMALIZATION_KEY][
            "rule"
        ] = "regla-desconocida"
    elif mutation == "normalization_rows":
        manifest["normalizations"][vps_migration.OPERATION_LOTE_NORMALIZATION_KEY][
            "rows"
        ] += 1
    elif mutation == "normalization_sha":
        manifest["normalizations"][vps_migration.OPERATION_LOTE_NORMALIZATION_KEY][
            "sha256"
        ] = ("z" * 64)
    elif mutation == "normalization_pairs":
        manifest["normalizations"][vps_migration.OPERATION_LOTE_NORMALIZATION_KEY][
            "pairs"
        ] = "no-es-lista"
    elif mutation == "source_quiesced":
        manifest["source_barrier"]["source_quiesced"] = False
    elif mutation == "source_transaction":
        manifest["source_barrier"]["sqlite_transaction"] = "BEGIN"
    elif mutation == "barrier_rows":
        manifest["idempotency_barrier"]["rows"] += 1
    elif mutation == "barrier_rows_float":
        manifest["idempotency_barrier"]["rows"] = float(
            manifest["idempotency_barrier"]["rows"]
        )
    elif mutation == "barrier_version_float":
        manifest["idempotency_barrier"]["version"] = 1.0
    elif mutation == "barrier_algorithm":
        manifest["idempotency_barrier"]["algorithm"] = "sha1"
    elif mutation == "barrier_sha":
        manifest["idempotency_barrier"]["sha256"] = "0" * 64
    elif mutation == "env_path":
        manifest["env_template"]["path"] = "../env.production"
    elif mutation == "env_bytes":
        manifest["env_template"]["bytes"] += 1
    elif mutation == "env_sha":
        manifest["env_template"]["sha256"] = "0" * 64
    else:
        filename, info = next(iter(manifest["certificate_files"].items()))
        manifest["certificate_files"][filename.upper()] = dict(info)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v3_convierte_json_invalido_en_error_funcional(tmp_path: Path) -> None:
    """JSON truncado nunca escapa como JSONDecodeError/KeyError al operador."""
    package = _build_historical_v3_package(tmp_path)
    (package / "manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="manifest"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v3_rechaza_clave_json_duplicada(tmp_path: Path) -> None:
    """Una clave repetida no puede colapsarse silenciosamente al parsear JSON."""
    package = _build_historical_v3_package(tmp_path)
    manifest_path = package / "manifest.json"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        serialized.replace(
            '"package_version": 3,',
            '"package_version": 3,\n  "package_version": 3,',
            1,
        ),
        encoding="utf-8",
    )
    assert manifest_path.read_text(encoding="utf-8").count('"package_version"') == 2

    with pytest.raises(vps_migration.MigrationError, match="clave duplicada"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("activo", "1"),
        ("activo", 2),
        ("archivo_key", "par-activo.pem"),
        ("archivo_key", "__same_as_crt__"),
    ],
)
def test_manifest_v4_rechaza_par_certificado_activo_no_canonico(
    tmp_path: Path,
    field_name: str,
    invalid_value: Any,
) -> None:
    """El loader exige 0/1 y un par basename `.crt`/`.key` distinto."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "certificados")
    if invalid_value == "__same_as_crt__":
        rows[0][field_name] = rows[0]["archivo_crt"]
    else:
        rows[0][field_name] = invalid_value
    _rewrite_package_jsonl_rows(package, manifest, "certificados", rows)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize("mutation", ["missing", "wrong_lote", "duplicate"])
def test_manifest_v4_reconstruye_pares_lote_normalizados(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Un sidecar autoconsistente no puede inventar ni omitir operaciones batch."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json={
            "lote": _lote_response_payload(),
            "mensaje": "Lote procesado",
            "en_progreso": False,
        },
    )
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    normalization = manifest["normalizations"][
        vps_migration.OPERATION_LOTE_NORMALIZATION_KEY
    ]
    if mutation == "missing":
        pairs: list[dict[str, Any]] = []
    elif mutation == "wrong_lote":
        pairs = [
            {
                "operacion_id": 140,
                "lote_id": 999,
                "grupo_ids": [],
                "grupos_rechazo_ids": [],
                "grupos_no_enviados_ids": [],
            }
        ]
    else:
        pairs = [
            {
                "operacion_id": 140,
                "lote_id": 130,
                "grupo_ids": [],
                "grupos_rechazo_ids": [],
                "grupos_no_enviados_ids": [],
            },
            {
                "operacion_id": 140,
                "lote_id": 130,
                "grupo_ids": [],
                "grupos_rechazo_ids": [],
                "grupos_no_enviados_ids": [],
            },
        ]
    normalization["pairs"] = pairs
    normalization["rows"] = len(pairs)
    normalization["sha256"] = hashlib.sha256(
        json.dumps(
            pairs,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="normaliz|pares|lote"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_reconstruye_digest_rece_desde_asociaciones(
    tmp_path: Path,
) -> None:
    """Eliminar una asociación moderna bloquea aunque se reatestigüe el JSONL."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    table_name = "operaciones_idempotentes_elegibilidad_rece"
    _rewrite_package_jsonl_rows(package, manifest, table_name, [])
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="RECE|elegibilidad_rece"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_incluye_asociaciones_en_barrera_idempotente(
    tmp_path: Path,
) -> None:
    """Una asociación alterada conserva digest fiscal pero rompe la barrera exacta."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    table_name = "operaciones_idempotentes_elegibilidad_rece"
    rows = _read_package_jsonl_rows(package, manifest, table_name)
    rows[0]["id"] += 1000
    _rewrite_package_jsonl_rows(package, manifest, table_name, rows)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="barrera idempotente"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "mutation",
    [
        "tipo_desconocido",
        "respuesta_vacia",
        "key_con_espacios",
        "empresa_inexistente",
    ],
)
def test_manifest_v4_rechaza_operacion_terminal_semanticamente_adulterada(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Hashes recalculados no convierten una autoridad de replay inválida en válida."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="fallido_verificado",
        tipo_operacion="emitir_comprobante",
        lote_id=None,
        response_json={
            "exito": False,
            "comprobante_id": None,
            "tipo_comprobante": 6,
            "punto_venta": 6,
            "numero": 124,
            "fecha": "2026-06-03",
            "cae": None,
            "cae_vencimiento": None,
            "total": "121.00",
            "mensaje": "No se solicitó CAE",
            "errores": ["Fallo verificado"],
            "requiere_reconciliacion": False,
            "categoria_error": "pre_arca_verificado",
        },
    )
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "operaciones_idempotentes")
    if mutation == "tipo_desconocido":
        rows[0]["tipo_operacion"] = "tipo_desconocido"
    elif mutation == "respuesta_vacia":
        rows[0]["response_json"] = {}
    elif mutation == "key_con_espacios":
        rows[0]["idempotency_key"] = " key-adulterada "
    else:
        rows[0]["empresa_id"] = 999
    _rewrite_package_jsonl_rows(
        package,
        manifest,
        "operaciones_idempotentes",
        rows,
    )
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_cruza_replay_individual_con_comprobante_incluido(
    tmp_path: Path,
) -> None:
    """Un DTO sintáctico con número fiscal adulterado no preserva autoridad."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        tipo_operacion="emitir_comprobante",
        lote_id=None,
        response_json={
            "exito": True,
            "comprobante_id": 110,
            "tipo_comprobante": 6,
            "punto_venta": 6,
            "numero": 123,
            "fecha": "2026-06-03",
            "cae": "12345678901234",
            "cae_vencimiento": "2026-06-13",
            "total": "121.00",
            "mensaje": "Comprobante autorizado",
            "errores": [],
            "requiere_reconciliacion": False,
            "categoria_error": None,
        },
    )
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "operaciones_idempotentes")
    response = json.loads(rows[0]["response_json"])
    response["numero"] = 999
    rows[0]["response_json"] = json.dumps(response, sort_keys=True)
    _rewrite_package_jsonl_rows(
        package,
        manifest,
        "operaciones_idempotentes",
        rows,
    )
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="comprobante"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize("invalid_value", ["true", 2])
def test_manifest_v4_rechaza_boolean_sqlite_no_canonico(
    tmp_path: Path,
    invalid_value: Any,
) -> None:
    """El loader no permite que la conversión de import altere privilegios."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "usuarios")
    rows[0]["es_admin"] = invalid_value
    _rewrite_package_jsonl_rows(package, manifest, "usuarios", rows)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="Boolean no canónico"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_convierte_numeric_invalido_en_error_funcional(
    tmp_path: Path,
) -> None:
    """Un Decimal adulterado nunca escapa como InvalidOperation al operador."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "comprobantes")
    rows[0]["total"] = "no-es-decimal"
    _rewrite_package_jsonl_rows(package, manifest, "comprobantes", rows)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="schema"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_mensaje_batch_negativo_no_textual(
    tmp_path: Path,
) -> None:
    """El replay de error batch conserva mensaje nulo o textual, nunca escalar."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="fallido_verificado",
        response_json={
            "categoria_error": "lote_no_procesable",
            "mensaje": "Fallo verificado",
            "errores": ["No se emitió"],
            "status_code": 409,
        },
    )
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "operaciones_idempotentes")
    response = json.loads(rows[0]["response_json"])
    response["mensaje"] = 123
    rows[0]["response_json"] = json.dumps(
        response,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    _rewrite_package_jsonl_rows(
        package,
        manifest,
        "operaciones_idempotentes",
        rows,
    )
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="batch|semánticamente"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize("mutation", ["numero_cero", "cae_vacio"])
def test_manifest_v4_rechaza_exito_individual_coordinadamente_adulterado(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Operación y comprobante no pueden coordinar evidencia fiscal inválida."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        tipo_operacion="emitir_comprobante",
        lote_id=None,
        response_json={
            "exito": True,
            "comprobante_id": 110,
            "tipo_comprobante": 6,
            "punto_venta": 6,
            "numero": 123,
            "fecha": "2026-06-03",
            "cae": "12345678901234",
            "cae_vencimiento": "2026-06-13",
            "total": "121.00",
            "mensaje": "Comprobante autorizado",
            "errores": [],
            "requiere_reconciliacion": False,
            "categoria_error": None,
        },
    )
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    operation_rows = _read_package_jsonl_rows(
        package,
        manifest,
        "operaciones_idempotentes",
    )
    receipt_rows = _read_package_jsonl_rows(package, manifest, "comprobantes")
    response = json.loads(operation_rows[0]["response_json"])
    if mutation == "numero_cero":
        response["numero"] = 0
        receipt_rows[0]["numero"] = 0
    else:
        response["cae"] = ""
        receipt_rows[0]["cae"] = ""
    operation_rows[0]["response_json"] = json.dumps(response, sort_keys=True)
    _rewrite_package_jsonl_rows(
        package,
        manifest,
        "operaciones_idempotentes",
        operation_rows,
    )
    _rewrite_package_jsonl_rows(
        package,
        manifest,
        "comprobantes",
        receipt_rows,
    )
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="evidencia fiscal"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize("extra_location", ["root", "data", "certs"])
def test_manifest_v4_rechaza_archivos_no_declarados(
    tmp_path: Path,
    extra_location: str,
) -> None:
    """El paquete no admite archivos extra fuera de su partición declarada."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    target = package if extra_location == "root" else package / extra_location
    (target / "extra.bin").write_bytes(b"extra")

    with pytest.raises(vps_migration.MigrationError):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_rechaza_schema_jsonl_aunque_actualicen_hash(
    tmp_path: Path,
) -> None:
    """Un JSONL sin todas las columnas falla aunque bytes/SHA se reatestigüen."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_path = package / manifest["data_files"]["empresas"]["path"]
    row = json.loads(data_path.read_text(encoding="utf-8").strip())
    row.pop("cuit")
    vps_migration.write_jsonl(data_path, [row])
    manifest["data_files"]["empresas"]["bytes"] = data_path.stat().st_size
    manifest["data_files"]["empresas"]["sha256"] = vps_migration.sha256_file(data_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="Schema JSONL"):
        vps_migration.load_and_verify_manifest(package)


def test_manifest_v4_recalcula_barrera_idempotente_desde_jsonl(
    tmp_path: Path,
) -> None:
    """Cambiar una key y su SHA de archivo no alcanza sin la barrera semántica."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json={
            "lote": _lote_response_payload(),
            "mensaje": "Lote procesado",
            "en_progreso": False,
        },
    )
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    operation_path = (
        package / manifest["data_files"]["operaciones_idempotentes"]["path"]
    )
    row = json.loads(operation_path.read_text(encoding="utf-8").strip())
    row["idempotency_key"] = "key-alterada"
    vps_migration.write_jsonl(operation_path, [row])
    info = manifest["data_files"]["operaciones_idempotentes"]
    info["bytes"] = operation_path.stat().st_size
    info["sha256"] = vps_migration.sha256_file(operation_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="barrera idempotente"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize("mutation", ["errores_arca", "texto_publico"])
def test_loader_bloquea_replay_10005_reatestiguado_sin_evidencia_canonica(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Reatestar archivo y barrera no permite degradar el DTO PF-19C."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_global_rejection(db_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "operaciones_idempotentes")
    response = json.loads(rows[0]["response_json"])
    if mutation == "errores_arca":
        response["errores_arca"] = []
    else:
        response["mensaje"] = "Reintentá inmediatamente"
        response["errores"] = []
    rows[0]["response_json"] = json.dumps(
        response,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    _rewrite_package_jsonl_rows(package, manifest, "operaciones_idempotentes", rows)
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(vps_migration.MigrationError, match="10005"):
        vps_migration.load_and_verify_manifest(package)


@pytest.mark.parametrize(
    "mutation",
    [
        "errores",
        "marker",
        "owner",
        "marker_fuera_inventario",
        "marker_otro_existente",
        "envelope",
    ],
)
def test_loader_bloquea_replay_batch_10005_reatestiguado_mutado(
    tmp_path: Path,
    mutation: str,
) -> None:
    """El loader reconstruye la evidencia batch aunque se reatestigüe el JSONL."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_pf19c_batch_global_rejection(db_path)
    if mutation == "marker_otro_existente":
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        try:
            with engine.begin() as conn:
                group = dict(
                    conn.execute(
                        select(Base.metadata.tables["lotes_comprobantes_grupos"]).where(
                            Base.metadata.tables["lotes_comprobantes_grupos"].c.id
                            == 160
                        )
                    )
                    .mappings()
                    .one()
                )
                group.update(id=161, comprobante_ref="VPS-2", orden=2)
                conn.execute(
                    Base.metadata.tables["lotes_comprobantes_grupos"].insert(),
                    group,
                )
                row = dict(
                    conn.execute(
                        select(Base.metadata.tables["lotes_comprobantes_filas"]).where(
                            Base.metadata.tables["lotes_comprobantes_filas"].c.id == 161
                        )
                    )
                    .mappings()
                    .one()
                )
                row.update(
                    id=162,
                    fila_excel=3,
                    comprobante_ref="VPS-2",
                    grupo_id=161,
                )
                conn.execute(
                    Base.metadata.tables["lotes_comprobantes_filas"].insert(),
                    row,
                )
                response = _batch_global_rejection_response()
                response["lote"].update(
                    {
                        "total_filas": 2,
                        "total_grupos": 2,
                        "grupos_fallidos": 2,
                    }
                )
                conn.execute(
                    Base.metadata.tables["lotes_comprobantes"]
                    .update()
                    .where(Base.metadata.tables["lotes_comprobantes"].c.id == 130)
                    .values(total_filas=2, total_grupos=2, grupos_fallidos=2)
                )
                conn.execute(
                    Base.metadata.tables["operaciones_idempotentes"]
                    .update()
                    .where(Base.metadata.tables["operaciones_idempotentes"].c.id == 140)
                    .values(response_json=response)
                )
        finally:
            engine.dispose()
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _read_package_jsonl_rows(package, manifest, "operaciones_idempotentes")
    response = json.loads(rows[0]["response_json"])
    if mutation == "envelope":
        response = {
            "categoria_error": "arca_rechazo_global_excluyente",
            "mensaje": "Resultado batch inválido",
            "errores": [],
            "status_code": 400,
        }
    elif mutation == "errores":
        response["errores_arca"] = []
    elif mutation == "owner":
        response["lote"]["metadata_json"]["pf19c_rechazo_global"]["operacion_id"] = 999
    elif mutation == "marker_fuera_inventario":
        response["lote"]["metadata_json"]["pf19c_rechazo_global"][
            "grupos_rechazo_ids"
        ] = [999]
    elif mutation == "marker_otro_existente":
        response["lote"]["metadata_json"]["pf19c_rechazo_global"][
            "grupos_rechazo_ids"
        ] = [161]
    else:
        response["lote"]["metadata_json"]["pf19c_rechazo_global"][
            "grupos_rechazo_ids"
        ] = []
    rows[0]["response_json"] = json.dumps(
        response,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    _rewrite_package_jsonl_rows(package, manifest, "operaciones_idempotentes", rows)
    _rebuild_manifest_idempotency_barrier(package, manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        vps_migration.MigrationError,
        match=(
            "10005|PF-19C|batch negativo|inventario fuente|roles de grupos fuente|"
            "normalización atribuye roles"
        ),
    ):
        vps_migration.load_and_verify_manifest(package)


def test_inserta_filas_preservando_ids_y_relaciones(tmp_path: Path) -> None:
    """La carga de filas del paquete debe preservar IDs y relaciones."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
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


class _RowResult:
    """Resultado mínimo compatible con `one()` para estado de secuencia."""

    def __init__(self, value: tuple[Any, ...]) -> None:
        self.value = value

    def one(self) -> tuple[Any, ...]:
        return self.value


class _FakeSequenceConnection:
    """Conexión fake para verificar llamadas PostgreSQL de secuencias."""

    def __init__(
        self,
        max_ids: dict[str, int | None],
        *,
        missing_sequences: set[str] | None = None,
        sequence_states: dict[str, tuple[int, bool]] | None = None,
    ) -> None:
        self.max_ids = max_ids
        self.missing_sequences = missing_sequences or set()
        self.sequence_states = sequence_states or {}
        self.current_table: str | None = None
        self.restarts: dict[str, int] = {}
        self.statements: list[str] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> Any:
        assert params is not None or "setval" not in str(statement)
        sql = str(statement)
        self.statements.append(sql)
        if "pg_get_serial_sequence" in sql:
            assert params is not None
            self.current_table = params["table_name"]
            if self.current_table in self.missing_sequences:
                return _ScalarResult(None)
            return _ScalarResult(f"{self.current_table}_id_seq")
        if "ALTER SEQUENCE" in sql:
            assert self.current_table is not None
            self.restarts[self.current_table] = int(sql.rsplit(" ", 1)[1])
            return _ScalarResult(None)
        if "last_value, is_called" in sql:
            assert self.current_table is not None
            return _RowResult(
                self.sequence_states.get(
                    self.current_table,
                    (self.restarts[self.current_table], False),
                )
            )
        assert self.current_table is not None
        return _ScalarResult(self.max_ids.get(self.current_table))


def test_ajusta_secuencias_al_maximo_id_restaurado() -> None:
    """Las secuencias deben quedar alineadas al mayor ID de cada tabla."""
    max_ids = {table_name: None for table_name in vps_migration.INCLUDED_TABLES}
    max_ids["empresas"] = 10
    max_ids["comprobantes"] = 110
    conn = _FakeSequenceConnection(max_ids)

    vps_migration.reset_postgres_sequences(conn)
    vps_migration.verify_postgres_sequences(conn)

    assert conn.restarts["empresas"] == 11
    assert conn.restarts["comprobantes"] == 111
    assert conn.restarts["usuarios"] == 1
    assert not any("setval" in statement for statement in conn.statements)
    assert not any("nextval" in statement for statement in conn.statements)


@pytest.mark.parametrize("phase", ["reset", "verify"])
def test_secuencias_fallan_cerrado_si_falta_relacion(phase: str) -> None:
    """Toda PK importada con ID debe conservar su secuencia PostgreSQL."""
    max_ids = {table_name: None for table_name in vps_migration.INCLUDED_TABLES}
    conn = _FakeSequenceConnection(
        max_ids,
        missing_sequences={"empresas"},
    )

    with pytest.raises(vps_migration.MigrationError, match="secuencia.*empresas"):
        if phase == "reset":
            vps_migration.reset_postgres_sequences(conn)
        else:
            vps_migration.verify_postgres_sequences(conn)


@pytest.mark.parametrize("sequence_state", [(12, False), (11, True)])
def test_verificacion_secuencia_no_consume_y_rechaza_estado_inexacto(
    sequence_state: tuple[int, bool],
) -> None:
    """`last_value/is_called` debe describir exactamente el próximo ID libre."""
    max_ids = {table_name: None for table_name in vps_migration.INCLUDED_TABLES}
    max_ids["empresas"] = 10
    conn = _FakeSequenceConnection(
        max_ids,
        sequence_states={"empresas": sequence_state},
    )
    vps_migration.reset_postgres_sequences(conn)

    with pytest.raises(vps_migration.MigrationError, match="próximo ID libre"):
        vps_migration.verify_postgres_sequences(conn)

    assert not any("nextval" in statement for statement in conn.statements)


class _ContextManager:
    """Context manager mínimo para simular conexiones SQLAlchemy."""

    def __init__(self, conn: object) -> None:
        self.conn = conn

    def __enter__(self) -> object:
        return self.conn

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _HeadResult:
    """Resultado mínimo iterable para filas de `alembic_version`."""

    def __init__(self, values: list[str]) -> None:
        self.values = values

    def scalars(self) -> list[str]:
        return self.values


class _HeadConnection:
    """Conexión fake que solo expone el conjunto Alembic destino."""

    def __init__(self, values: list[str]) -> None:
        self.values = values

    def execute(self, statement: Any) -> _HeadResult:
        return _HeadResult(self.values)


class _FakeEngine:
    """Engine fake para verificar orden de importación."""

    def __init__(self) -> None:
        self.conn = object()
        self.disposed = False

    def connect(self) -> _ContextManager:
        return _ContextManager(self.conn)

    def begin(self) -> _ContextManager:
        return _ContextManager(self.conn)

    def dispose(self) -> None:
        """Registra la liberación explícita del pool fake."""
        self.disposed = True


class _SingleTransactionEngine:
    """Engine que rechaza cualquier conexión fuera de la única transacción."""

    def __init__(self, events: list[str]) -> None:
        self.conn = object()
        self.events = events
        self.disposed = False

    def connect(self) -> _ContextManager:
        raise AssertionError("import_package no debe abrir un precheck separado")

    def begin(self) -> _ContextManager:
        self.events.append("begin")
        return _ContextManager(self.conn)

    def dispose(self) -> None:
        """Registra la liberación explícita del pool fake."""
        self.disposed = True


class _FailingCommitContext(_ContextManager):
    """Transacción fake que simula un error al confirmar sin error previo."""

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        if exc_type is None:
            raise vps_migration.MigrationError("commit fallido")
        return False


class _FailingCommitEngine:
    """Engine fake para comprobar cleanup posterior al rollback/commit fallido."""

    def __init__(self) -> None:
        self.conn = object()
        self.disposed = False

    def connect(self) -> _ContextManager:
        raise AssertionError("No debe abrir una conexión separada")

    def begin(self) -> _FailingCommitContext:
        return _FailingCommitContext(self.conn)

    def dispose(self) -> None:
        """Registra la liberación tras un commit ambiguo."""
        self.disposed = True


class _RecordingTransactionContext(_ContextManager):
    """Registra si el context manager recibió una excepción del cuerpo."""

    def __init__(self, conn: object, events: list[str]) -> None:
        super().__init__(conn)
        self.events = events

    def __enter__(self) -> object:
        self.events.append("tx-enter")
        return super().__enter__()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        name = getattr(exc_type, "__name__", "none")
        self.events.append(f"tx-exit:{name}")
        return False


class _RecordingTransactionEngine:
    """Engine fake para observar rollback del cuerpo sin otra conexión."""

    def __init__(self, events: list[str]) -> None:
        self.conn = object()
        self.events = events
        self.disposed = False

    def connect(self) -> _ContextManager:
        raise AssertionError("No debe abrir una conexión separada")

    def begin(self) -> _RecordingTransactionContext:
        return _RecordingTransactionContext(self.conn, self.events)

    def dispose(self) -> None:
        """Registra la liberación explícita tras commit o rollback."""
        self.disposed = True


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
                f"CERTS_PATH={path.parent / 'target-certs'}",
            ]
        ),
        encoding="utf-8",
    )


def _insert_canonical_target_seed(conn: Any) -> None:
    """Inserta el único seed Alembic que B2 está autorizado a reemplazar."""
    config = vps_migration._load_canonical_alembic_seed_config()
    now = datetime(2026, 8, 9, 12, 0, 0)
    tables = Base.metadata.tables
    conn.execute(
        tables["formatos_importacion"].insert(),
        {
            "id": 1,
            "nombre": "Extracto bancario - creditos IVA exento",
            "descripcion": (
                "Formato global para extractos donde Creditos es el importe, "
                "Leyendas Adicionales1 el receptor, Leyendas Adicionales2 el "
                "documento y Pto Vta el punto de venta."
            ),
            "alcance": "global",
            "activo": True,
            "created_at": now,
            "updated_at": now,
            "empresa_id": None,
        },
    )
    conn.execute(
        tables["formatos_importacion_versiones"].insert(),
        {
            "id": 1,
            "version": 1,
            "estado": "vigente",
            "configuracion_json": config,
            "headers_firma_json": {
                "requeridos": ["Creditos", "Pto Vta"],
                "opcionales": [
                    "Fecha",
                    "Leyendas Adicionales1",
                    "Leyendas Adicionales2",
                ],
            },
            "created_at": now,
            "formato_id": 1,
        },
    )
    for field_id, (field_name, field_config) in enumerate(
        config["campos"].items(), start=1
    ):
        conn.execute(
            tables["formatos_importacion_campos"].insert(),
            {
                "id": field_id,
                "campo_destino": field_name,
                "origen_tipo": field_config.get("origen", "header"),
                "encabezado": (field_config.get("encabezados") or [None])[0],
                "alias_json": field_config.get("encabezados"),
                "valor_constante_json": field_config.get("valor"),
                "requerido": bool(field_config.get("requerido", False)),
                "transformacion": field_config.get("transformacion"),
                "valor_default_json": field_config.get("default"),
                "created_at": now,
                "version_id": 1,
            },
        )
    conn.execute(
        tables["formatos_importacion_reglas"].insert(),
        {
            "id": 1,
            "nombre": "Cada fila genera un comprobante",
            "tipo": "agrupacion",
            "configuracion_json": {"modo": "fila"},
            "orden": 1,
            "activo": True,
            "created_at": now,
            "version_id": 1,
        },
    )


def test_plantilla_env_usa_certs_path_runtime(tmp_path: Path) -> None:
    """La plantilla de VPS debe usar la variable de certificados del runtime."""
    env_path = tmp_path / ".env.production.example"

    vps_migration.write_env_template(env_path)

    content = env_path.read_text(encoding="utf-8")
    assert "CERTS_PATH=./certs" in content
    assert "FACTUFLOW_CERTS_DIR" not in content


def test_parsea_env_con_bom_de_powershell(tmp_path: Path) -> None:
    """El importador debe aceptar `.env` UTF-8 con BOM de Windows PowerShell."""
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    content = env_path.read_text(encoding="utf-8")
    env_path.write_text(content, encoding="utf-8-sig")

    values = vps_migration.parse_env_file(env_path)

    assert values["APP_SECRET_KEY"] == "clave"
    assert values["ARCA_PRIVATE_KEY_PASSWORD"] == "clave-destino-larga"


@pytest.mark.parametrize(
    "read_error",
    [
        PermissionError("denegado"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "inválido"),
    ],
)
def test_parse_env_sanitiza_archivo_ilegible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    read_error: Exception,
) -> None:
    """Permisos/encoding del entorno producen un error funcional controlado."""
    env_path = tmp_path / ".env.production"
    env_path.write_text("APP_SECRET_KEY=clave", encoding="utf-8")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(read_error),
    )

    with pytest.raises(vps_migration.MigrationError, match="UTF-8"):
        vps_migration.parse_env_file(env_path)


@pytest.mark.parametrize(
    ("target_heads", "manifest_head", "accepted"),
    [
        (["head-vigente"], vps_migration_v3.ALEMBIC_HEAD, True),
        ([], vps_migration_v3.ALEMBIC_HEAD, False),
        (["head-vigente", "otro-head"], vps_migration_v3.ALEMBIC_HEAD, False),
        (["otro-head"], vps_migration_v3.ALEMBIC_HEAD, False),
        (["head-vigente"], "otro-head", False),
    ],
)
def test_target_exige_head_vigente_y_manifest_historico_v3(
    monkeypatch: pytest.MonkeyPatch,
    target_heads: list[str],
    manifest_head: str,
    accepted: bool,
) -> None:
    """El destino sigue al repo; el manifest conserva el head histórico v3."""
    monkeypatch.setattr(
        vps_migration,
        "get_repo_alembic_head",
        lambda: "head-vigente",
    )
    conn = _HeadConnection(target_heads)
    manifest = {"package_version": 3, "alembic_version": manifest_head}

    if accepted:
        vps_migration.validate_target_alembic_head(conn, manifest)
    else:
        with pytest.raises(vps_migration.MigrationError, match="head Alembic"):
            vps_migration.validate_target_alembic_head(conn, manifest)


def test_import_bloquea_todas_las_tablas_en_orden_determinista() -> None:
    """El postflight queda protegido contra writers y otro importador."""

    class CaptureConnection:
        """Conexión mínima que captura el SQL de lock."""

        def __init__(self) -> None:
            self.statements: list[str] = []

        def execute(self, statement: Any) -> None:
            self.statements.append(str(statement))

    conn = CaptureConnection()
    vps_migration.lock_target_tables_for_import(conn)

    assert len(conn.statements) == 1
    statement = conn.statements[0]
    assert statement.startswith('LOCK TABLE "alembic_version", ')
    assert statement.endswith(" IN SHARE ROW EXCLUSIVE MODE")
    for table_name in {
        *vps_migration.INCLUDED_TABLES,
        *vps_migration.EXCLUDED_TABLES,
        *vps_migration.V3_ADAPTER_TARGET_EMPTY_TABLES,
    }:
        assert statement.count(f'"{table_name}"') == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_format",
        "missing_rule",
        "changed_config",
        "changed_field",
        "changed_column_position",
    ],
)
def test_target_solo_autoriza_borrar_seed_alembic_canonico(
    mutation: str,
) -> None:
    """Datos arbitrarios en formatos nunca se confunden con seeds reemplazables."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    tables = Base.metadata.tables
    with engine.begin() as conn:
        _insert_canonical_target_seed(conn)
        vps_migration.validate_canonical_target_seeds(conn)
        if mutation == "extra_format":
            conn.execute(
                tables["formatos_importacion"].insert(),
                {
                    "id": 999,
                    "nombre": "Formato ajeno",
                    "alcance": "global",
                    "activo": True,
                    "created_at": datetime(2026, 8, 9, 12, 0, 0),
                    "updated_at": datetime(2026, 8, 9, 12, 0, 0),
                },
            )
        elif mutation == "missing_rule":
            conn.execute(tables["formatos_importacion_reglas"].delete())
        elif mutation == "changed_config":
            conn.execute(
                tables["formatos_importacion_versiones"]
                .update()
                .values(configuracion_json={"tipo": "adulterado", "campos": {}})
            )
        elif mutation == "changed_field":
            conn.execute(
                tables["formatos_importacion_campos"]
                .update()
                .where(tables["formatos_importacion_campos"].c.id == 1)
                .values(transformacion="adulterada")
            )
        else:
            conn.execute(
                tables["formatos_importacion_campos"]
                .update()
                .where(tables["formatos_importacion_campos"].c.id == 1)
                .values(letra_columna="ZZ", indice_columna=999)
            )

        with pytest.raises(vps_migration.MigrationError, match="seed|campos"):
            vps_migration.validate_canonical_target_seeds(conn)


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
        source_quiesced=True,
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
        lambda *args: events.append("ready"),
    )
    monkeypatch.setattr(
        vps_migration,
        "lock_target_tables_for_import",
        lambda *args: events.append("lock"),
    )
    monkeypatch.setattr(
        vps_migration,
        "materialize_certificate_restore",
        fail_restore,
    )
    monkeypatch.setattr(
        vps_migration,
        "clear_seeded_included_tables",
        lambda *args: events.append("clear"),
    )
    monkeypatch.setattr(
        vps_migration,
        "insert_rows",
        lambda conn, table_name, rows: events.append(f"insert:{table_name}"),
    )
    monkeypatch.setattr(
        vps_migration,
        "reset_postgres_sequences",
        lambda *args: events.append("seq"),
    )
    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        lambda *args: events.append("postflight"),
    )
    monkeypatch.setattr(
        vps_migration,
        "verify_postgres_sequences",
        lambda *args: events.append("seq-check"),
    )

    with pytest.raises(vps_migration.MigrationError, match="sin permisos"):
        vps_migration.import_package(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
        )

    assert events == ["lock", "ready", "restore"]


def test_import_usa_una_sola_conexion_transaccional(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Precheck, carga y secuencias no se separan en conexiones observables."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    events: list[str] = []
    engine = _SingleTransactionEngine(events)

    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration,
        "lock_target_tables_for_import",
        lambda *args: events.append("lock"),
    )
    monkeypatch.setattr(
        vps_migration,
        "ensure_target_database_ready",
        lambda *args: events.append("ready"),
    )
    monkeypatch.setattr(
        vps_migration,
        "lock_target_tables_for_import",
        lambda *args: events.append("lock"),
    )
    monkeypatch.setattr(
        vps_migration,
        "restore_certificate_files",
        lambda *args, **kwargs: events.append("restore"),
    )
    monkeypatch.setattr(
        vps_migration,
        "clear_seeded_included_tables",
        lambda *args: events.append("clear"),
    )
    monkeypatch.setattr(
        vps_migration,
        "insert_rows",
        lambda conn, table_name, rows: events.append(f"insert:{table_name}"),
    )
    monkeypatch.setattr(
        vps_migration,
        "restore_deferred_columns",
        lambda *args: events.append("deferred"),
    )
    monkeypatch.setattr(
        vps_migration,
        "regenerate_v3_coordinators",
        lambda *args: events.append("coordinators"),
    )
    monkeypatch.setattr(
        vps_migration,
        "reset_postgres_sequences",
        lambda *args: events.append("seq"),
    )
    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        lambda *args: events.append("postflight"),
    )
    monkeypatch.setattr(
        vps_migration,
        "verify_postgres_sequences",
        lambda *args: events.append("seq-check"),
    )
    monkeypatch.setattr(
        vps_migration,
        "materialize_certificate_restore",
        lambda plan, journal: events.append("restore"),
    )
    monkeypatch.setattr(
        vps_migration,
        "verify_restored_certificate_files",
        lambda certs, manifest, password, rows: events.append("cert-check"),
    )

    vps_migration.import_package(
        package_dir=package,
        database_url="postgresql+psycopg2://user:pass@localhost/db",
        production_env=env_path,
    )

    assert events[0:5] == ["begin", "lock", "ready", "restore", "clear"]
    assert events[-4:] == [
        "postflight",
        "seq",
        "seq-check",
        "cert-check",
    ]
    assert engine.disposed is True


def test_journal_certificados_limpia_solo_archivos_creados(tmp_path: Path) -> None:
    """Un rollback preserva el material idéntico que ya existía antes del intento."""
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_crt = source_dir / "cert.crt"
    source_key = source_dir / "cert.key"
    source_crt.write_bytes(b"crt-sintetico")
    source_key.write_bytes(b"key-sintetica")
    target_crt = target_dir / source_crt.name
    target_crt.write_bytes(source_crt.read_bytes())
    crt_item = vps_migration.CertificateRestoreItem(
        filename=source_crt.name,
        source=source_crt,
        destination=target_crt,
        sha256=vps_migration.sha256_file(source_crt),
        existed=True,
    )
    key_item = vps_migration.CertificateRestoreItem(
        filename=source_key.name,
        source=source_key,
        destination=target_dir / source_key.name,
        sha256=vps_migration.sha256_file(source_key),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(
        target_dir=target_dir,
        items=(crt_item, key_item),
    )
    journal = vps_migration.CertificateRestoreJournal(created=[])

    vps_migration.materialize_certificate_restore(plan, journal)
    assert [item.filename for item in journal.created] == ["cert.key"]

    vps_migration.cleanup_certificate_restore(journal)

    assert target_crt.read_bytes() == b"crt-sintetico"
    assert not (target_dir / "cert.key").exists()


def test_materializacion_certificado_no_pisa_archivo_concurrente(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La publicación exclusiva preserva un basename creado por otro proceso."""
    source = tmp_path / "source.crt"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    source.write_bytes(b"propio")
    destination = target_dir / "cert.crt"
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=source,
        destination=destination,
        sha256=vps_migration.sha256_file(source),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(target_dir, (item,))
    journal = vps_migration.CertificateRestoreJournal(created=[])
    real_link = vps_migration.os.link

    def concurrent_link(source_path: Path, destination_path: Path) -> None:
        Path(destination_path).write_bytes(b"ajeno")
        real_link(source_path, destination_path)

    monkeypatch.setattr(vps_migration.os, "link", concurrent_link)

    with pytest.raises(vps_migration.MigrationError, match="colisión"):
        vps_migration.materialize_certificate_restore(plan, journal)

    assert destination.read_bytes() == b"ajeno"
    assert journal.created == []


def test_interrupcion_tras_publicar_certificado_limpia_propiedad_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una interrupción justo tras publicar no deja un archivo sin journal."""
    source = tmp_path / "source.key"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    source.write_bytes(b"propio")
    destination = target_dir / "cert.key"
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=source,
        destination=destination,
        sha256=vps_migration.sha256_file(source),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(target_dir, (item,))
    journal = vps_migration.CertificateRestoreJournal(created=[])
    real_link = vps_migration.os.link

    def interrupted_link(source_path: Path, destination_path: Path) -> None:
        real_link(source_path, destination_path)
        raise KeyboardInterrupt

    monkeypatch.setattr(vps_migration.os, "link", interrupted_link)

    with pytest.raises(KeyboardInterrupt):
        vps_migration.materialize_certificate_restore(plan, journal)

    assert not destination.exists()
    assert journal.created == []


def test_fallo_compensatorio_conserva_publicacion_en_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si no puede despublicar tras un fallo, retiene identidad para recovery."""
    source = tmp_path / "source.key"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    source.write_bytes(b"propio")
    destination = target_dir / "cert.key"
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=source,
        destination=destination,
        sha256=vps_migration.sha256_file(source),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(target_dir, (item,))
    journal = vps_migration.CertificateRestoreJournal(created=[])
    real_link = vps_migration.os.link
    real_lstat = vps_migration.os.lstat
    real_unlink = Path.unlink
    state = {"linked": False, "stat_failed": False}

    def tracked_link(source_path: Path, destination_path: Path) -> None:
        real_link(source_path, destination_path)
        state["linked"] = True

    def fail_first_target_lstat(path: Any, *args: Any, **kwargs: Any):
        if Path(path) == destination and state["linked"] and not state["stat_failed"]:
            state["stat_failed"] = True
            raise OSError("stat interrumpido")
        return real_lstat(path, *args, **kwargs)

    def fail_target_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == destination:
            raise PermissionError("no se pudo retirar")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(vps_migration.os, "link", tracked_link)
    monkeypatch.setattr(vps_migration.os, "lstat", fail_first_target_lstat)
    monkeypatch.setattr(Path, "unlink", fail_target_unlink)

    with pytest.raises(OSError, match="stat interrumpido"):
        vps_migration.materialize_certificate_restore(plan, journal)

    assert destination.exists()
    assert journal.created == [item]
    assert destination in journal.identities
    assert vps_migration.cleanup_certificate_restore(journal) is False
    assert journal.created == [item]


def test_stat_persistente_tras_link_conserva_ownership_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si no puede inspeccionar el hardlink, nunca declara cleanup completo."""
    source = tmp_path / "source.key"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    source.write_bytes(b"propio")
    destination = target_dir / "cert.key"
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=source,
        destination=destination,
        sha256=vps_migration.sha256_file(source),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(target_dir, (item,))
    journal = vps_migration.CertificateRestoreJournal(created=[])
    real_link = vps_migration.os.link
    real_lstat = vps_migration.os.lstat
    real_stat = vps_migration.os.stat
    state = {"linked": False}

    def tracked_link(source_path: Path, destination_path: Path) -> None:
        real_link(source_path, destination_path)
        state["linked"] = True

    def persistent_lstat(path: Any, *args: Any, **kwargs: Any):
        if state["linked"] and Path(path) == destination:
            raise OSError("stat persistente")
        return real_lstat(path, *args, **kwargs)

    def persistent_stat(path: Any, *args: Any, **kwargs: Any):
        if state["linked"] and Path(path) == destination:
            raise OSError("stat persistente")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(vps_migration.os, "link", tracked_link)
    monkeypatch.setattr(vps_migration.os, "lstat", persistent_lstat)
    monkeypatch.setattr(vps_migration.os, "stat", persistent_stat)

    with pytest.raises(OSError, match="stat persistente"):
        vps_migration.materialize_certificate_restore(plan, journal)

    assert real_lstat(destination)
    assert journal.created == [item]
    assert journal.identities[destination]
    assert vps_migration.cleanup_certificate_restore(journal) is False


def test_temporal_sensible_no_se_pierde_si_unlink_falla(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un staging que no pudo borrarse queda journalizado como cleanup incompleto."""
    source = tmp_path / "source.key"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    source.write_bytes(b"propio")
    destination = target_dir / "cert.key"
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=source,
        destination=destination,
        sha256=vps_migration.sha256_file(source),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(target_dir, (item,))
    journal = vps_migration.CertificateRestoreJournal(created=[])
    real_unlink = Path.unlink

    def fail_temp_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name.startswith(".factuflow-vps-"):
            raise PermissionError("temp bloqueado")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_temp_unlink)

    with pytest.raises(PermissionError, match="temp bloqueado"):
        vps_migration.materialize_certificate_restore(plan, journal)

    assert destination.exists()
    assert len(journal.temporary) == 1
    assert vps_migration.cleanup_certificate_restore(journal) is False
    assert not destination.exists()
    assert len(journal.temporary) == 1


def test_copia_por_descriptor_no_sobrescribe_hardlink_ajeno(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reemplazar el pathname temporal no redirige la escritura sensible."""
    source = tmp_path / "source.key"
    sentinel = tmp_path / "sentinel.bin"
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    source.write_bytes(b"clave-propia")
    sentinel.write_bytes(b"contenido-ajeno")
    destination = target_dir / "cert.key"
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=source,
        destination=destination,
        sha256=vps_migration.sha256_file(source),
        existed=False,
    )
    plan = vps_migration.CertificateRestorePlan(target_dir, (item,))
    journal = vps_migration.CertificateRestoreJournal(created=[])
    real_copy = vps_migration._copy_certificate_source_to_descriptor
    attack_state = {"mode": "pending"}

    def replace_path_before_copy(source_path: Path, descriptor: int) -> str:
        temp_path = next(target_dir.glob(".factuflow-vps-*.tmp"))
        try:
            temp_path.unlink()
        except PermissionError:
            attack_state["mode"] = "blocked_by_open_descriptor"
            return real_copy(source_path, descriptor)
        vps_migration.os.link(sentinel, temp_path)
        attack_state["mode"] = "replaced"
        return real_copy(source_path, descriptor)

    monkeypatch.setattr(
        vps_migration,
        "_copy_certificate_source_to_descriptor",
        replace_path_before_copy,
    )

    caught: vps_migration.MigrationError | None = None
    try:
        vps_migration.materialize_certificate_restore(plan, journal)
    except vps_migration.MigrationError as exc:
        caught = exc

    assert sentinel.read_bytes() == b"contenido-ajeno"
    if attack_state["mode"] == "blocked_by_open_descriptor":
        assert caught is None
        assert destination.read_bytes() == b"clave-propia"
        assert journal.created == [item]
        assert vps_migration.cleanup_certificate_restore(journal) is True
        assert not destination.exists()
    else:
        assert caught is not None
        assert "temporal" in str(caught)
        foreign_temp = next(target_dir.glob(".factuflow-vps-*.tmp"))
        assert vps_migration.os.path.samefile(sentinel, foreign_temp)
        assert not destination.exists()
        assert journal.created == []
        assert journal.temporary == {}
        assert vps_migration.cleanup_certificate_restore(journal) is True


def test_cleanup_incompleto_conserva_evidencia_en_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un archivo que no pudo retirarse no desaparece del journal operativo."""
    destination = tmp_path / "cert.key"
    destination.write_bytes(b"propio")
    item = vps_migration.CertificateRestoreItem(
        filename=destination.name,
        source=tmp_path / "source.key",
        destination=destination,
        sha256=vps_migration.sha256_file(destination),
        existed=False,
    )
    journal = vps_migration.CertificateRestoreJournal(created=[item])
    real_unlink = Path.unlink

    def denied_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path == destination:
            raise PermissionError("denegado")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied_unlink)

    assert vps_migration.cleanup_certificate_restore(journal) is False
    assert journal.created == [item]
    assert destination.exists()


def test_import_commit_ambiguo_conserva_certificados_para_validar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un commit incierto conserva claves por si la base sí quedó confirmada."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    target_dir = tmp_path / "target-certs"
    target_dir.mkdir()
    preexisting_name = next(iter(manifest["certificate_files"]))
    preexisting_info = manifest["certificate_files"][preexisting_name]
    preexisting_path = target_dir / preexisting_name
    preexisting_path.write_bytes((package / preexisting_info["path"]).read_bytes())

    engine = _FailingCommitEngine()
    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration,
        "ensure_target_database_ready",
        lambda *args: None,
    )
    monkeypatch.setattr(
        vps_migration,
        "lock_target_tables_for_import",
        lambda *args: None,
    )
    monkeypatch.setattr(
        vps_migration, "clear_seeded_included_tables", lambda *args: None
    )
    monkeypatch.setattr(
        vps_migration,
        "insert_rows",
        lambda conn, table_name, rows: None,
    )
    monkeypatch.setattr(vps_migration, "restore_deferred_columns", lambda *args: None)
    monkeypatch.setattr(vps_migration, "regenerate_v3_coordinators", lambda *args: None)
    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        lambda *args: None,
    )
    monkeypatch.setattr(vps_migration, "reset_postgres_sequences", lambda *args: None)
    monkeypatch.setattr(vps_migration, "verify_postgres_sequences", lambda *args: None)

    with pytest.raises(vps_migration.MigrationError, match="estado incierto"):
        vps_migration.import_package(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
            target_certs_dir=target_dir,
        )

    assert preexisting_path.is_file()
    assert vps_migration.sha256_file(preexisting_path) == preexisting_info["sha256"]
    assert {path.name for path in target_dir.iterdir()} == set(
        manifest["certificate_files"]
    )
    assert engine.disposed is True


def test_import_postflight_fallido_revierte_y_limpia_solo_archivos_propios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo del cuerpo hace rollback antes de limpiar los certs creados."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    target_dir = tmp_path / "target-certs"
    events: list[str] = []
    engine = _RecordingTransactionEngine(events)

    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration,
        "ensure_target_database_ready",
        lambda *args: events.append("ready"),
    )
    monkeypatch.setattr(
        vps_migration,
        "lock_target_tables_for_import",
        lambda *args: events.append("lock"),
    )
    monkeypatch.setattr(
        vps_migration,
        "clear_seeded_included_tables",
        lambda *args: events.append("clear"),
    )
    monkeypatch.setattr(vps_migration, "insert_rows", lambda *args: None)
    monkeypatch.setattr(vps_migration, "restore_deferred_columns", lambda *args: None)
    monkeypatch.setattr(
        vps_migration,
        "regenerate_v3_coordinators",
        lambda *args: events.append("coordinators"),
    )

    def fail_postflight(*args: Any) -> None:
        events.append("postflight")
        raise vps_migration.MigrationError("postflight inválido")

    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        fail_postflight,
    )

    with pytest.raises(vps_migration.MigrationError, match="postflight inválido"):
        vps_migration.import_package(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
            target_certs_dir=target_dir,
        )

    assert events == [
        "tx-enter",
        "lock",
        "ready",
        "clear",
        "coordinators",
        "postflight",
        "tx-exit:MigrationError",
    ]
    assert not target_dir.exists() or not list(target_dir.iterdir())
    assert engine.disposed is True


def test_import_sanitiza_fallo_del_cuerpo_y_limpia_certificados(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Errores inesperados no exponen datos y conservan rollback determinista."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    target_dir = tmp_path / "target-certs"
    events: list[str] = []
    engine = _RecordingTransactionEngine(events)

    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration, "lock_target_tables_for_import", lambda *args: None
    )
    monkeypatch.setattr(
        vps_migration,
        "ensure_target_database_ready",
        lambda *args: None,
    )
    monkeypatch.setattr(
        vps_migration,
        "clear_seeded_included_tables",
        lambda *args: None,
    )

    def fail_insert(*args: Any) -> None:
        raise RuntimeError("dato-fiscal-secreto")

    monkeypatch.setattr(vps_migration, "insert_rows", fail_insert)

    with pytest.raises(vps_migration.MigrationError) as caught:
        vps_migration.import_package(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
            target_certs_dir=target_dir,
        )

    assert "dato-fiscal-secreto" not in str(caught.value)
    assert events[-1] == "tx-exit:RuntimeError"
    assert not target_dir.exists() or not list(target_dir.iterdir())
    assert engine.disposed is True


def test_validate_import_reutiliza_postflight_y_secuencias_integrales(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La validación standalone repite la autoridad semántica de B2."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    engine = _FakeEngine()
    events: list[str] = []

    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration,
        "lock_target_tables_for_import",
        lambda *args: events.append("lock"),
    )

    def postflight(conn: object, manifest: dict, rows: dict, contract: Any) -> None:
        assert conn is engine.conn
        assert set(rows) == set(contract.included_tables)
        events.append("postflight")

    def sequence_check(conn: object, contract: Any) -> None:
        assert conn is engine.conn
        events.append("seq-check")

    monkeypatch.setattr(vps_migration, "validate_imported_database", postflight)
    monkeypatch.setattr(vps_migration, "verify_postgres_sequences", sequence_check)
    monkeypatch.setattr(
        vps_migration,
        "verify_restored_certificate_files",
        lambda *args: events.append("cert-check"),
    )

    vps_migration.validate_import(
        package_dir=package,
        database_url="postgresql+psycopg2://user:pass@localhost/db",
        production_env=env_path,
    )

    assert events == ["lock", "postflight", "seq-check", "cert-check"]
    assert engine.disposed is True


@pytest.mark.parametrize(
    ("target_state", "expected_message"),
    [
        ("clean", "reintento es seguro"),
        ("partial", "requiere intervención"),
    ],
)
def test_validate_clasifica_commit_no_confirmado_sin_reimportar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_state: str,
    expected_message: str,
) -> None:
    """Validate distingue rollback limpio de una restauración parcial."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    engine = _FakeEngine()

    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration, "lock_target_tables_for_import", lambda *args: None
    )
    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        lambda *args: (_ for _ in ()).throw(
            vps_migration.MigrationError("estado no confirmado")
        ),
    )
    if target_state == "clean":
        monkeypatch.setattr(
            vps_migration,
            "ensure_target_database_ready",
            lambda *args: None,
        )
        monkeypatch.setattr(
            vps_migration,
            "verify_restored_certificate_files",
            lambda *args: None,
        )
    else:
        monkeypatch.setattr(
            vps_migration,
            "ensure_target_database_ready",
            lambda *args: (_ for _ in ()).throw(
                vps_migration.MigrationError("estado parcial")
            ),
        )

    with pytest.raises(vps_migration.MigrationError, match=expected_message):
        vps_migration.validate_import(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
        )


def test_validate_sanitiza_error_inesperado_sin_ocultar_interrupciones(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El borde CLI no filtra detalles, pero respeta cancelaciones operativas."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    engine = _FakeEngine()

    monkeypatch.setattr(vps_migration, "create_postgres_engine", lambda url: engine)
    monkeypatch.setattr(
        vps_migration, "lock_target_tables_for_import", lambda *args: None
    )
    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        lambda *args: (_ for _ in ()).throw(RuntimeError("dato-fiscal-secreto")),
    )

    with pytest.raises(vps_migration.MigrationError) as caught:
        vps_migration.validate_import(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
        )
    assert "dato-fiscal-secreto" not in str(caught.value)

    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    with pytest.raises(KeyboardInterrupt):
        vps_migration.validate_import(
            package_dir=package,
            database_url="postgresql+psycopg2://user:pass@localhost/db",
            production_env=env_path,
        )


def test_precarga_jsonl_queda_ligada_al_manifest_verificado(tmp_path: Path) -> None:
    """Una mutación posterior al loader no entra al snapshot de importación."""
    db_path, certs_dir = _create_source_db(tmp_path)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    data_path = package / manifest["data_files"]["empresas"]["path"]
    data_path.write_bytes(data_path.read_bytes() + b" ")

    with pytest.raises(vps_migration.MigrationError, match="cambió"):
        vps_migration.read_package_rows(package, manifest, "empresas")


def test_postflight_valida_snapshot_completo_antes_del_commit(tmp_path: Path) -> None:
    """El estado transaccional exacto y su ledger pasan antes de confirmar."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    engine, package_rows = _load_package_into_sqlite_target(package, manifest)
    try:
        with engine.connect() as conn:
            vps_migration.validate_imported_database(conn, manifest, package_rows)
    finally:
        engine.dispose()


def test_postflight_rechaza_revision_fiscal_regresiva() -> None:
    """El ledger restaurado conserva monotonía fiscal además de revisiones 1..N."""
    rows = {
        "puntos_venta": [
            {"id": 40, "empresa_id": 10, "revision_fiscal": 2},
        ],
        "puntos_venta_elegibilidad_rece_revisiones": [
            {
                "id": 41,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "revision": 1,
                "punto_revision_fiscal": 2,
            },
            {
                "id": 42,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "revision": 2,
                "punto_revision_fiscal": 1,
            },
            {
                "id": 43,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "homologacion",
                "revision": 1,
                "punto_revision_fiscal": 1,
            },
        ],
        "puntos_venta_elegibilidad_rece_actual": [
            {
                "id": 44,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "produccion",
                "revision_actual_id": 42,
            },
            {
                "id": 45,
                "empresa_id": 10,
                "punto_venta_id": 40,
                "ambiente": "homologacion",
                "revision_actual_id": 43,
            },
        ],
    }

    with pytest.raises(vps_migration.MigrationError, match="retrocede"):
        vps_migration.validate_rece_ledger_rows(rows)


@pytest.mark.parametrize(
    "mutation",
    [
        "included_value",
        "excluded_row",
        "ledger_previous_head",
        "ledger_gap",
        "rece_digest",
        "lote_id",
        "barrier",
    ],
)
def test_postflight_rechaza_estado_mismo_conteo_o_fiscalmente_incoherente(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Conteos iguales no ocultan contenido distinto ni un ledger RECE roto."""
    db_path, certs_dir = _create_source_db(tmp_path)
    if mutation in {"rece_digest", "lote_id"}:
        _insert_terminal_guard_context(db_path, with_attempt=True)
    package = vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    engine, package_rows = _load_package_into_sqlite_target(package, manifest)
    tables = Base.metadata.tables
    try:
        with engine.begin() as conn:
            if mutation == "included_value":
                conn.execute(
                    tables["puntos_venta"]
                    .update()
                    .where(tables["puntos_venta"].c.id == 40)
                    .values(nombre="Nombre adulterado")
                )
            elif mutation == "excluded_row":
                conn.execute(
                    tables["eventos_sistema"].insert(),
                    {
                        "id": 1,
                        "accion": "adulteracion",
                        "categoria": "test",
                        "estado": "exitoso",
                        "bytes_afectados": 0,
                        "created_at": datetime(2026, 8, 9, 12, 0, 0),
                    },
                )
            elif mutation == "ledger_previous_head":
                conn.execute(
                    tables["puntos_venta_elegibilidad_rece_actual"]
                    .update()
                    .where(tables["puntos_venta_elegibilidad_rece_actual"].c.id == 44)
                    .values(revision_actual_id=41)
                )
                package_rows["puntos_venta_elegibilidad_rece_actual"][1][
                    "revision_actual_id"
                ] = 41
            elif mutation == "ledger_gap":
                base_revision = dict(
                    package_rows["puntos_venta_elegibilidad_rece_revisiones"][1]
                )
                base_revision.update({"id": 99, "revision": 3})
                conn.execute(
                    tables["puntos_venta_elegibilidad_rece_revisiones"].insert(),
                    base_revision,
                )
                conn.execute(
                    tables["puntos_venta_elegibilidad_rece_actual"]
                    .update()
                    .where(tables["puntos_venta_elegibilidad_rece_actual"].c.id == 44)
                    .values(revision_actual_id=99)
                )
                package_rows["puntos_venta_elegibilidad_rece_revisiones"].append(
                    base_revision
                )
                package_rows["puntos_venta_elegibilidad_rece_actual"][1][
                    "revision_actual_id"
                ] = 99
                manifest["included_counts"][
                    "puntos_venta_elegibilidad_rece_revisiones"
                ] += 1
            if mutation == "rece_digest":
                operation = package_rows["operaciones_idempotentes"][0]
                operation["rece_snapshot_hash"] = "0" * 64
                conn.execute(
                    tables["operaciones_idempotentes"]
                    .update()
                    .where(
                        tables["operaciones_idempotentes"].c.id == int(operation["id"])
                    )
                    .values(rece_snapshot_hash="0" * 64)
                )
            elif mutation == "lote_id":
                operation = package_rows["operaciones_idempotentes"][0]
                operation["lote_id"] = 999
                conn.execute(
                    tables["operaciones_idempotentes"]
                    .update()
                    .where(
                        tables["operaciones_idempotentes"].c.id == int(operation["id"])
                    )
                    .values(lote_id=999)
                )
            elif mutation == "barrier":
                manifest["idempotency_barrier"]["sha256"] = "0" * 64

            with pytest.raises(vps_migration.MigrationError):
                vps_migration.validate_imported_database(
                    conn,
                    manifest,
                    package_rows,
                )
    finally:
        engine.dispose()
