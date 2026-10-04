"""Contrato histórico inmutable para leer paquetes de migración v3.

Este módulo describe el schema del head ``f4a5b6c7d8e9`` sin consultar el ORM
vigente. El ORM actual se usa después, exclusivamente como destino explícito de
la adaptación.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

PACKAGE_VERSION = 3
ALEMBIC_HEAD = "f4a5b6c7d8e9"
SCOPE = "operacion_futura_con_comprobantes"
ENV_TEMPLATE_FILENAME = "env.production.required.example"
REQUIRED_ENV_KEYS = (
    "APP_SECRET_KEY",
    "ARCA_PRIVATE_KEY_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "ARCA_ENV",
    "CORS_ORIGINS",
    "VITE_API_URL",
    "CERTS_PATH",
)
PACKAGE_NOTES = (
    "No incluye lotes, filas, temporales, PDFs, Excels, logs ni cache ARCA.",
    "Las claves privadas se re-cifraron con ARCA_PRIVATE_KEY_PASSWORD destino.",
    "La SQLite local debe conservarse como evidencia histórica privada.",
)
MANIFEST_TOP_LEVEL_KEYS = frozenset(
    {
        "package_version",
        "created_at",
        "scope",
        "alembic_version",
        "included_tables",
        "excluded_tables",
        "target_empty_tables",
        "included_counts",
        "excluded_counts",
        "active_certificates",
        "safe_omitted",
        "normalizations",
        "source_barrier",
        "idempotency_barrier",
        "data_files",
        "certificate_files",
        "env_template",
        "required_env_keys",
        "notes",
    }
)
DATA_FILE_INFO_KEYS = frozenset({"path", "sha256", "rows", "bytes"})
CERTIFICATE_FILE_INFO_KEYS = frozenset({"path", "sha256", "bytes"})
ENV_TEMPLATE_INFO_KEYS = frozenset({"path", "sha256", "bytes"})
NORMALIZATION_INFO_KEYS = frozenset({"rule", "rows", "sha256", "pairs"})
SOURCE_BARRIER_KEYS = frozenset(
    {"source_quiesced", "sqlite_transaction", "data_version"}
)
IDEMPOTENCY_BARRIER_KEYS = frozenset({"version", "algorithm", "rows", "sha256"})
OPERATION_LOTE_NORMALIZATION_KEY = "operaciones_idempotentes.lote_id"
OPERATION_LOTE_NORMALIZATION_RULE = (
    "set_null_preserve_source_pairs_and_group_inventory_sha256_v2"
)
IDEMPOTENCY_BARRIER_ALGORITHM = "sha256-json-c14n-v1"
AMBIENTES_RECE = frozenset({"homologacion", "produccion"})
ESTADOS_OPERACION_TERMINALES = frozenset(
    {"finalizado", "fallido", "fallido_verificado", "rechazado_arca"}
)
ESTADOS_LOTE_SEGUROS_OMITIBLES = frozenset(
    {
        "cargado",
        "validado",
        "con_errores",
        "completado",
        "fallido",
        "autorizado_parcial",
        "cerrado_con_descartes",
        "cerrado_reconciliado",
    }
)
ARCA_RECHAZO_GLOBAL_CATEGORIA = "arca_rechazo_global_excluyente"
ARCA_RECHAZO_GLOBAL_MENSAJE = (
    "El punto de venta no está dado de alta como RECE en ARCA."
)
ARCA_RECHAZO_GLOBAL_INDIVIDUAL_MENSAJE = (
    "ARCA rechazó el requerimiento completo antes de autorizar."
)
ARCA_RECHAZO_GLOBAL_INDIVIDUAL_ERRORES = (
    "Revisá la habilitación RECE del punto de venta antes de iniciar otra emisión.",
)
ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE = (
    "ARCA rechazó un requerimiento completo y FactuFlow detuvo los "
    "grupos restantes sin enviarlos."
)
ARCA_RECHAZO_GLOBAL_ERRORES = (
    {
        "codigo": 10005,
        "alcance": "global",
        "mensaje": ARCA_RECHAZO_GLOBAL_MENSAJE,
    },
)
LEGACY_PF19_CATEGORIA = "legacy_sin_autorizacion_verificada"
LEGACY_PF19_MENSAJE = "Cierre legacy por ausencia de autorización verificada"


@dataclass(frozen=True)
class ColumnSpec:
    """Tipo, nulabilidad e identidad histórica de una columna v3."""

    kind: str
    nullable: bool = False
    primary_key: bool = False
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    timezone: bool | None = None


@dataclass(frozen=True)
class ForeignKeySpec:
    """FK histórica, incluida la composición y el orden de sus columnas."""

    local_columns: tuple[str, ...]
    remote_table: str
    remote_columns: tuple[str, ...]
    ondelete: str | None = None
    onupdate: str | None = None


def _c(kind: str, nullable: bool = False, primary_key: bool = False) -> ColumnSpec:
    return ColumnSpec(kind, nullable, primary_key)


V3_COLUMNS: dict[str, dict[str, ColumnSpec]] = {
    "empresas": {
        "id": _c("integer", primary_key=True),
        "razon_social": _c("string"),
        "cuit": _c("string"),
        "condicion_iva": _c("string"),
        "ingresos_brutos": _c("string", True),
        "domicilio": _c("string"),
        "localidad": _c("string"),
        "provincia": _c("string"),
        "codigo_postal": _c("string"),
        "email": _c("string", True),
        "telefono": _c("string", True),
        "inicio_actividades": _c("date"),
        "logo": _c("string", True),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
    },
    "usuarios": {
        "id": _c("integer", primary_key=True),
        "email": _c("string"),
        "hashed_password": _c("string"),
        "nombre": _c("string"),
        "activo": _c("boolean"),
        "es_admin": _c("boolean"),
        "puede_crear_editar_emisores": _c("boolean"),
        "empresa_id": _c("integer", True),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
        "ultimo_login": _c("datetime", True),
        "password_changed_at": _c("datetime", True),
    },
    "usuario_emisor_acceso": {
        "usuario_id": _c("integer", primary_key=True),
        "empresa_id": _c("integer", primary_key=True),
        "otorgado_por_usuario_id": _c("integer", True),
        "origen": _c("string"),
        "otorgado_en": _c("datetime"),
    },
    "clientes": {
        "id": _c("integer", primary_key=True),
        "razon_social": _c("string"),
        "tipo_documento": _c("string"),
        "numero_documento": _c("string"),
        "condicion_iva": _c("string"),
        "domicilio": _c("string", True),
        "localidad": _c("string", True),
        "provincia": _c("string", True),
        "codigo_postal": _c("string", True),
        "email": _c("string", True),
        "telefono": _c("string", True),
        "notas": _c("string", True),
        "activo": _c("boolean"),
        "empresa_id": _c("integer"),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
    },
    "puntos_venta": {
        "id": _c("integer", primary_key=True),
        "numero": _c("integer"),
        "nombre": _c("string", True),
        "sistema": _c("string", True),
        "domicilio": _c("string", True),
        "domicilio_fuente": _c("string", True),
        "nombre_fantasia": _c("string", True),
        "nombre_fantasia_fuente": _c("string", True),
        "es_webservice": _c("boolean"),
        "bloqueado": _c("boolean"),
        "fecha_baja": _c("string", True),
        "fuente": _c("string", True),
        "activo": _c("boolean"),
        "usar_en_factuflow": _c("boolean"),
        "revision_fiscal": _c("integer"),
        "ultima_comprobacion_arca_en": _c("datetime", True),
        "empresa_id": _c("integer"),
        "created_at": _c("datetime"),
    },
    "puntos_venta_elegibilidad_rece_revisiones": {
        "id": _c("integer", primary_key=True),
        "empresa_id": _c("integer"),
        "punto_venta_id": _c("integer"),
        "ambiente": _c("string"),
        "revision": _c("integer"),
        "estado": _c("string"),
        "fuente": _c("string"),
        "evidencia_tipo": _c("string"),
        "evidencia_sha256": _c("string", True),
        "clasificador_version": _c("string", True),
        "empresa_cuit_snapshot": _c("string", True),
        "punto_venta_numero_snapshot": _c("integer", True),
        "punto_revision_fiscal": _c("integer"),
        "documento_emitido_en": _c("date", True),
        "vigente_hasta": _c("date", True),
        "observado_en": _c("datetime"),
        "verificado_en": _c("datetime", True),
        "creado_por_usuario_id": _c("integer", True),
        "actor_usuario_id_snapshot": _c("integer", True),
        "created_at": _c("datetime"),
    },
    "puntos_venta_elegibilidad_rece_actual": {
        "id": _c("integer", primary_key=True),
        "empresa_id": _c("integer"),
        "punto_venta_id": _c("integer"),
        "ambiente": _c("string"),
        "revision_actual_id": _c("integer"),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
    },
    "operaciones_idempotentes": {
        "id": _c("integer", primary_key=True),
        "idempotency_key": _c("string"),
        "tipo_operacion": _c("string"),
        "payload_hash": _c("string"),
        "estado": _c("string"),
        "response_json": _c("json", True),
        "error_json": _c("json", True),
        "rece_snapshot_hash": _c("string", True),
        "lote_id": _c("integer", True),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
        "empresa_id": _c("integer"),
        "usuario_id": _c("integer", True),
    },
    "operaciones_idempotentes_elegibilidad_rece": {
        "id": _c("integer", primary_key=True),
        "operacion_id": _c("integer"),
        "empresa_id": _c("integer"),
        "punto_venta_id": _c("integer"),
        "ambiente": _c("string"),
        "elegibilidad_revision_id": _c("integer"),
        "punto_venta_revision_fiscal": _c("integer"),
        "created_at": _c("datetime"),
    },
    "certificados": {
        "id": _c("integer", primary_key=True),
        "nombre": _c("string"),
        "cuit": _c("string"),
        "fecha_emision": _c("date"),
        "fecha_vencimiento": _c("date"),
        "archivo_crt": _c("string"),
        "archivo_key": _c("string"),
        "activo": _c("boolean"),
        "ambiente": _c("string"),
        "empresa_id": _c("integer"),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
    },
    "formatos_importacion": {
        "id": _c("integer", primary_key=True),
        "nombre": _c("string"),
        "descripcion": _c("string", True),
        "alcance": _c("string"),
        "activo": _c("boolean"),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
        "empresa_id": _c("integer", True),
    },
    "formatos_importacion_versiones": {
        "id": _c("integer", primary_key=True),
        "version": _c("integer"),
        "estado": _c("string"),
        "configuracion_json": _c("json"),
        "headers_firma_json": _c("json", True),
        "created_at": _c("datetime"),
        "formato_id": _c("integer"),
    },
    "formatos_importacion_campos": {
        "id": _c("integer", primary_key=True),
        "campo_destino": _c("string"),
        "origen_tipo": _c("string"),
        "encabezado": _c("string", True),
        "alias_json": _c("json", True),
        "letra_columna": _c("string", True),
        "indice_columna": _c("integer", True),
        "valor_constante_json": _c("json", True),
        "requerido": _c("boolean"),
        "transformacion": _c("string", True),
        "valor_default_json": _c("json", True),
        "created_at": _c("datetime"),
        "version_id": _c("integer"),
    },
    "formatos_importacion_reglas": {
        "id": _c("integer", primary_key=True),
        "nombre": _c("string"),
        "tipo": _c("string"),
        "configuracion_json": _c("json", True),
        "orden": _c("integer"),
        "activo": _c("boolean"),
        "created_at": _c("datetime"),
        "version_id": _c("integer"),
    },
    "perfiles_carga_masiva": {
        "id": _c("integer", primary_key=True),
        "nombre": _c("string"),
        "descripcion": _c("string", True),
        "configuracion_json": _c("json"),
        "es_predeterminado": _c("boolean"),
        "activo": _c("boolean"),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
        "empresa_id": _c("integer"),
    },
    "comprobantes": {
        "id": _c("integer", primary_key=True),
        "tipo_comprobante": _c("integer"),
        "concepto": _c("integer"),
        "numero": _c("integer"),
        "fecha_emision": _c("date"),
        "fecha_vencimiento": _c("date", True),
        "fecha_servicio_desde": _c("date", True),
        "fecha_servicio_hasta": _c("date", True),
        "fecha_vto_pago": _c("date", True),
        "subtotal": _c("numeric"),
        "descuento": _c("numeric"),
        "iva_21": _c("numeric"),
        "iva_10_5": _c("numeric"),
        "iva_27": _c("numeric"),
        "otros_impuestos": _c("numeric"),
        "total": _c("numeric"),
        "cae": _c("string", True),
        "cae_vencimiento": _c("date", True),
        "estado": _c("string"),
        "origen_emision": _c("string"),
        "moneda": _c("string"),
        "cotizacion": _c("numeric"),
        "observaciones": _c("string", True),
        "empresa_id": _c("integer"),
        "punto_venta_id": _c("integer"),
        "cliente_id": _c("integer", True),
        "receptor_tipo_documento": _c("integer", True),
        "receptor_numero_documento": _c("string", True),
        "receptor_razon_social": _c("string", True),
        "receptor_condicion_iva": _c("string", True),
        "receptor_domicilio": _c("string", True),
        "created_at": _c("datetime"),
        "updated_at": _c("datetime"),
    },
    "comprobante_items": {
        "id": _c("integer", primary_key=True),
        "codigo": _c("string", True),
        "descripcion": _c("string"),
        "cantidad": _c("numeric"),
        "unidad": _c("string"),
        "precio_unitario": _c("numeric"),
        "descuento_porcentaje": _c("numeric"),
        "iva_porcentaje": _c("numeric"),
        "subtotal": _c("numeric"),
        "orden": _c("integer"),
        "comprobante_id": _c("integer"),
    },
}

_STRING_LENGTHS: dict[str, dict[str, int]] = {
    "empresas": {
        "razon_social": 255,
        "cuit": 11,
        "condicion_iva": 50,
        "ingresos_brutos": 50,
        "domicilio": 255,
        "localidad": 100,
        "provincia": 100,
        "codigo_postal": 10,
        "email": 255,
        "telefono": 50,
        "logo": 255,
    },
    "usuarios": {"email": 255, "hashed_password": 255, "nombre": 255},
    "usuario_emisor_acceso": {"origen": 30},
    "clientes": {
        "razon_social": 255,
        "tipo_documento": 20,
        "numero_documento": 20,
        "condicion_iva": 50,
        "domicilio": 255,
        "localidad": 100,
        "provincia": 100,
        "codigo_postal": 10,
        "email": 255,
        "telefono": 50,
        "notas": 500,
    },
    "puntos_venta": {
        "nombre": 255,
        "sistema": 255,
        "domicilio": 500,
        "domicilio_fuente": 30,
        "nombre_fantasia": 255,
        "nombre_fantasia_fuente": 30,
        "fecha_baja": 20,
        "fuente": 50,
    },
    "puntos_venta_elegibilidad_rece_revisiones": {
        "ambiente": 20,
        "estado": 30,
        "fuente": 40,
        "evidencia_tipo": 50,
        "evidencia_sha256": 64,
        "clasificador_version": 40,
        "empresa_cuit_snapshot": 11,
    },
    "puntos_venta_elegibilidad_rece_actual": {"ambiente": 20},
    "operaciones_idempotentes": {
        "idempotency_key": 128,
        "tipo_operacion": 50,
        "payload_hash": 64,
        "estado": 40,
        "rece_snapshot_hash": 64,
    },
    "operaciones_idempotentes_elegibilidad_rece": {"ambiente": 20},
    "certificados": {
        "nombre": 255,
        "cuit": 11,
        "archivo_crt": 255,
        "archivo_key": 255,
        "ambiente": 20,
    },
    "formatos_importacion": {"nombre": 120, "alcance": 20},
    "formatos_importacion_versiones": {"estado": 20},
    "formatos_importacion_campos": {
        "campo_destino": 100,
        "origen_tipo": 20,
        "encabezado": 255,
        "letra_columna": 10,
        "transformacion": 50,
    },
    "formatos_importacion_reglas": {"nombre": 120, "tipo": 50},
    "perfiles_carga_masiva": {"nombre": 120},
    "comprobantes": {
        "cae": 14,
        "estado": 20,
        "origen_emision": 30,
        "moneda": 3,
        "observaciones": 500,
        "receptor_numero_documento": 20,
        "receptor_razon_social": 255,
        "receptor_condicion_iva": 50,
        "receptor_domicilio": 255,
    },
    "comprobante_items": {
        "codigo": 50,
        "descripcion": 500,
        "unidad": 50,
    },
}

_NUMERIC_DIMENSIONS: dict[str, dict[str, tuple[int, int]]] = {
    "comprobantes": {
        "subtotal": (12, 2),
        "descuento": (12, 2),
        "iva_21": (12, 2),
        "iva_10_5": (12, 2),
        "iva_27": (12, 2),
        "otros_impuestos": (12, 2),
        "total": (12, 2),
        "cotizacion": (10, 6),
    },
    "comprobante_items": {
        "cantidad": (10, 4),
        "precio_unitario": (12, 4),
        "descuento_porcentaje": (5, 2),
        "iva_porcentaje": (5, 2),
        "subtotal": (12, 2),
    },
}

_TEXT_COLUMNS = {
    ("formatos_importacion", "descripcion"),
    ("perfiles_carga_masiva", "descripcion"),
}

for _table_name, _columns in V3_COLUMNS.items():
    for _column_name, _spec in tuple(_columns.items()):
        if (_table_name, _column_name) in _TEXT_COLUMNS:
            _columns[_column_name] = replace(_spec, kind="text")
        elif _spec.kind == "string":
            _columns[_column_name] = replace(
                _spec,
                length=_STRING_LENGTHS[_table_name][_column_name],
            )
        elif _spec.kind == "numeric":
            _precision, _scale = _NUMERIC_DIMENSIONS[_table_name][_column_name]
            _columns[_column_name] = replace(
                _spec,
                precision=_precision,
                scale=_scale,
            )
        elif _spec.kind == "datetime":
            _columns[_column_name] = replace(_spec, timezone=False)

INCLUDED_TABLES = tuple(V3_COLUMNS)

EXCLUDED_TABLES = (
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

OPERATIONAL_TARGET_EMPTY_TABLES = (
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
)
TARGET_EMPTY_TABLES = OPERATIONAL_TARGET_EMPTY_TABLES + EXCLUDED_TABLES
SAFE_OMITTED_COUNT_KEYS = {
    "intentos_emision_fiscal": "intentos_terminales_omitidos",
    "resoluciones_legacy_pf19_journal": "resoluciones_legacy_pf19_omitidas",
    "puntos_venta_guardas_emision_rece": "guardas_terminales_omitidas",
    "lotes_comprobantes": "lotes_seguros_omitidos",
    "lotes_comprobantes_grupos": "grupos_seguros_omitidos",
    "lotes_comprobantes_filas": "filas_omitidas",
    "lotes_comprobantes_eventos": "eventos_lote_omitidos",
    "eventos_sistema": "eventos_sistema_omitidos",
    "exportaciones_almacenamiento": "exportaciones_omitidas",
}
SAFE_OMITTED_KEYS = frozenset(
    {
        "blockers",
        "excluded_counts",
        "operaciones_terminales_preservadas",
        "operaciones_lote_normalizado",
        "asociaciones_rece_preservadas",
        *SAFE_OMITTED_COUNT_KEYS.values(),
    }
)

FOREIGN_KEYS: dict[str, tuple[ForeignKeySpec, ...]] = {
    "usuarios": (ForeignKeySpec(("empresa_id",), "empresas", ("id",)),),
    "usuario_emisor_acceso": (
        ForeignKeySpec(("usuario_id",), "usuarios", ("id",)),
        ForeignKeySpec(("empresa_id",), "empresas", ("id",)),
        ForeignKeySpec(("otorgado_por_usuario_id",), "usuarios", ("id",)),
    ),
    "clientes": (ForeignKeySpec(("empresa_id",), "empresas", ("id",)),),
    "puntos_venta": (ForeignKeySpec(("empresa_id",), "empresas", ("id",)),),
    "puntos_venta_elegibilidad_rece_revisiones": (
        ForeignKeySpec(
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
        ),
        ForeignKeySpec(("creado_por_usuario_id",), "usuarios", ("id",)),
    ),
    "puntos_venta_elegibilidad_rece_actual": (
        ForeignKeySpec(
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
        ),
        ForeignKeySpec(
            ("revision_actual_id", "empresa_id", "punto_venta_id", "ambiente"),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
        ),
    ),
    "operaciones_idempotentes": (
        ForeignKeySpec(("empresa_id",), "empresas", ("id",)),
        ForeignKeySpec(("usuario_id",), "usuarios", ("id",)),
        ForeignKeySpec(("lote_id",), "lotes_comprobantes", ("id",)),
    ),
    "operaciones_idempotentes_elegibilidad_rece": (
        ForeignKeySpec(
            ("operacion_id", "empresa_id"),
            "operaciones_idempotentes",
            ("id", "empresa_id"),
        ),
        ForeignKeySpec(
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
        ),
        ForeignKeySpec(
            ("elegibilidad_revision_id", "empresa_id", "punto_venta_id", "ambiente"),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
        ),
    ),
    "certificados": (ForeignKeySpec(("empresa_id",), "empresas", ("id",)),),
    "formatos_importacion": (ForeignKeySpec(("empresa_id",), "empresas", ("id",)),),
    "formatos_importacion_versiones": (
        ForeignKeySpec(("formato_id",), "formatos_importacion", ("id",)),
    ),
    "formatos_importacion_campos": (
        ForeignKeySpec(("version_id",), "formatos_importacion_versiones", ("id",)),
    ),
    "formatos_importacion_reglas": (
        ForeignKeySpec(("version_id",), "formatos_importacion_versiones", ("id",)),
    ),
    "perfiles_carga_masiva": (ForeignKeySpec(("empresa_id",), "empresas", ("id",)),),
    "comprobantes": (
        ForeignKeySpec(("empresa_id",), "empresas", ("id",)),
        ForeignKeySpec(("punto_venta_id",), "puntos_venta", ("id",)),
        ForeignKeySpec(("cliente_id",), "clientes", ("id",)),
    ),
    "comprobante_items": (
        ForeignKeySpec(("comprobante_id",), "comprobantes", ("id",)),
    ),
}

_FOREIGN_KEY_ACTIONS: dict[tuple[str, tuple[str, ...]], str] = {
    ("usuarios", ("empresa_id",)): "SET NULL",
    ("usuario_emisor_acceso", ("usuario_id",)): "CASCADE",
    ("usuario_emisor_acceso", ("empresa_id",)): "CASCADE",
    ("usuario_emisor_acceso", ("otorgado_por_usuario_id",)): "SET NULL",
    ("clientes", ("empresa_id",)): "RESTRICT",
    ("puntos_venta", ("empresa_id",)): "RESTRICT",
    (
        "puntos_venta_elegibilidad_rece_revisiones",
        ("punto_venta_id", "empresa_id"),
    ): "RESTRICT",
    (
        "puntos_venta_elegibilidad_rece_revisiones",
        ("creado_por_usuario_id",),
    ): "SET NULL",
    (
        "puntos_venta_elegibilidad_rece_actual",
        ("punto_venta_id", "empresa_id"),
    ): "RESTRICT",
    (
        "puntos_venta_elegibilidad_rece_actual",
        ("revision_actual_id", "empresa_id", "punto_venta_id", "ambiente"),
    ): "RESTRICT",
    ("operaciones_idempotentes", ("empresa_id",)): "RESTRICT",
    ("operaciones_idempotentes", ("usuario_id",)): "SET NULL",
    ("operaciones_idempotentes", ("lote_id",)): "SET NULL",
    (
        "operaciones_idempotentes_elegibilidad_rece",
        ("operacion_id", "empresa_id"),
    ): "CASCADE",
    (
        "operaciones_idempotentes_elegibilidad_rece",
        ("punto_venta_id", "empresa_id"),
    ): "RESTRICT",
    (
        "operaciones_idempotentes_elegibilidad_rece",
        ("elegibilidad_revision_id", "empresa_id", "punto_venta_id", "ambiente"),
    ): "RESTRICT",
    ("certificados", ("empresa_id",)): "RESTRICT",
    ("formatos_importacion", ("empresa_id",)): "RESTRICT",
    ("formatos_importacion_versiones", ("formato_id",)): "CASCADE",
    ("formatos_importacion_campos", ("version_id",)): "CASCADE",
    ("formatos_importacion_reglas", ("version_id",)): "CASCADE",
    ("perfiles_carga_masiva", ("empresa_id",)): "RESTRICT",
    ("comprobantes", ("empresa_id",)): "RESTRICT",
    ("comprobantes", ("punto_venta_id",)): "RESTRICT",
    ("comprobantes", ("cliente_id",)): "RESTRICT",
    ("comprobante_items", ("comprobante_id",)): "CASCADE",
}

FOREIGN_KEYS = {
    table_name: tuple(
        replace(
            foreign_key,
            ondelete=_FOREIGN_KEY_ACTIONS[(table_name, foreign_key.local_columns)],
        )
        for foreign_key in foreign_keys
    )
    for table_name, foreign_keys in FOREIGN_KEYS.items()
}

TARGET_NULL_ADDITIONS: dict[str, tuple[str, ...]] = {
    "operaciones_idempotentes": (
        "control_duplicados_json",
        "duplicados_version",
        "duplicados_generacion_id",
        "operacion_raiz_id",
        "solicitante_nombre_snapshot",
        "solicitud_emision_at",
    )
}

SEEDED_INCLUDED_TABLES = (
    "formatos_importacion",
    "formatos_importacion_versiones",
    "formatos_importacion_campos",
    "formatos_importacion_reglas",
)
ADAPTER_TARGET_EMPTY_TABLES = (
    "lotes_duplicados_coordinacion",
    "lotes_duplicados_evidencias",
    "lotes_duplicados_coincidencias",
    "lotes_duplicados_coincidencias_miembros",
)
PRIMARY_KEYS = {
    table_name: tuple(
        column_name for column_name, column in columns.items() if column.primary_key
    )
    for table_name, columns in V3_COLUMNS.items()
}
SEQUENCE_TABLES = tuple(
    table_name
    for table_name, primary_key in PRIMARY_KEYS.items()
    if primary_key == ("id",)
)


@dataclass(frozen=True)
class ImportContract:
    """Contrato seleccionado una vez para todo el camino de importación."""

    package_version: int
    alembic_head: str
    included_tables: tuple[str, ...]
    excluded_tables: tuple[str, ...]
    target_empty_tables: tuple[str, ...]
    seeded_included_tables: tuple[str, ...]
    adapter_target_empty_tables: tuple[str, ...]
    sequence_tables: tuple[str, ...]


V3_CONTRACT = ImportContract(
    package_version=PACKAGE_VERSION,
    alembic_head=ALEMBIC_HEAD,
    included_tables=INCLUDED_TABLES,
    excluded_tables=EXCLUDED_TABLES,
    target_empty_tables=TARGET_EMPTY_TABLES,
    seeded_included_tables=SEEDED_INCLUDED_TABLES,
    adapter_target_empty_tables=ADAPTER_TARGET_EMPTY_TABLES,
    sequence_tables=SEQUENCE_TABLES,
)


def validate_value(spec: ColumnSpec, value: Any) -> Any:
    """Valida el tipo JSON histórico y devuelve el valor de destino."""
    if value is None:
        if spec.primary_key or not spec.nullable:
            raise ValueError("null no permitido")
        return None
    if spec.kind == "boolean":
        if isinstance(value, bool) or not isinstance(value, int) or value not in {0, 1}:
            raise ValueError("booleano no canónico")
        return bool(value)
    if spec.kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("entero inválido")
        return value
    if spec.kind in {"string", "text"}:
        if not isinstance(value, str):
            raise ValueError("texto inválido")
        if spec.length is not None and len(value) > spec.length:
            raise ValueError("texto excede la longitud histórica")
        return value
    if spec.kind == "date":
        if not isinstance(value, str):
            raise ValueError("fecha inválida")
        return date.fromisoformat(value)
    if spec.kind == "datetime":
        if not isinstance(value, str):
            raise ValueError("fecha y hora inválida")
        converted_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
        is_aware = (
            converted_datetime.tzinfo is not None
            and converted_datetime.utcoffset() is not None
        )
        if spec.timezone is not None and is_aware != spec.timezone:
            raise ValueError("zona horaria incompatible con el tipo histórico")
        return converted_datetime
    if spec.kind == "numeric":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError("numérico inválido")
        converted = Decimal(str(value))
        if not converted.is_finite():
            raise ValueError("numérico no finito")
        if spec.precision is not None and spec.scale is not None:
            quantum = Decimal(1).scaleb(-spec.scale)
            try:
                with localcontext() as context:
                    context.prec = max(
                        50,
                        len(converted.as_tuple().digits)
                        + abs(converted.as_tuple().exponent)
                        + spec.precision,
                    )
                    if converted != converted.quantize(quantum):
                        raise ValueError(
                            "numérico requiere redondeo para el tipo histórico"
                        )
            except InvalidOperation as exc:
                raise ValueError("numérico incompatible con el tipo histórico") from exc
            integer_digits = (
                max(converted.copy_abs().adjusted() + 1, 0) if converted else 0
            )
            if integer_digits > spec.precision - spec.scale:
                raise ValueError("numérico excede la precisión histórica")
        return converted
    if spec.kind == "json":
        return json.loads(value) if isinstance(value, str) else value
    raise ValueError(f"tipo histórico desconocido: {spec.kind}")


@dataclass(frozen=True)
class ReplayArcaError:
    codigo: int
    alcance: str
    mensaje: str


@dataclass(frozen=True)
class IndividualReplay:
    exito: bool
    comprobante_id: int | None
    tipo_comprobante: int
    punto_venta: int
    numero: int
    fecha: date
    cae: str | None
    cae_vencimiento: date | None
    total: Decimal
    mensaje: str
    errores: tuple[str, ...]
    errores_arca: tuple[ReplayArcaError, ...]
    requiere_reconciliacion: bool
    categoria_error: str | None


@dataclass(frozen=True)
class BatchLotReplay:
    id: int
    estado: str
    empresa_id: int


@dataclass(frozen=True)
class BatchReplay:
    lote: BatchLotReplay
    mensaje: str
    en_progreso: bool | None
    errores_arca: tuple[ReplayArcaError, ...]


@dataclass(frozen=True)
class BatchErrorReplay:
    categoria_error: str
    mensaje: str | None
    errores: tuple[str, ...] | None
    status_code: int | None


def _exact_object(
    value: Any,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not required.issubset(value)
        or not set(value).issubset(required | optional)
    ):
        raise ValueError("shape de replay v3 inválido")
    return value


def _replay_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("entero de replay v3 inválido")
    return value


def _replay_bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("booleano de replay v3 inválido")
    return value


def _replay_string(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("texto de replay v3 inválido")
    return value


def _replay_optional_string(value: Any) -> str | None:
    return None if value is None else _replay_string(value)


def _replay_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("fecha de replay v3 inválida")
    return date.fromisoformat(value)


def _replay_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp de replay v3 inválido")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _replay_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("decimal de replay v3 inválido")
    converted = Decimal(str(value))
    if not converted.is_finite():
        raise ValueError("decimal de replay v3 no finito")
    return converted


def _replay_optional_int(value: Any) -> int | None:
    return None if value is None else _replay_int(value)


def _replay_errors(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("lista de errores de replay v3 inválida")
    return tuple(value)


def _replay_arca_errors(value: Any) -> tuple[ReplayArcaError, ...]:
    if not isinstance(value, list):
        raise ValueError("errores ARCA de replay v3 inválidos")
    result: list[ReplayArcaError] = []
    for raw_error in value:
        error = _exact_object(
            raw_error,
            required=frozenset({"codigo", "alcance", "mensaje"}),
        )
        alcance = _replay_string(error["alcance"])
        if alcance != "global":
            raise ValueError("alcance ARCA de replay v3 inválido")
        result.append(
            ReplayArcaError(
                codigo=_replay_int(error["codigo"]),
                alcance=alcance,
                mensaje=_replay_string(error["mensaje"]),
            )
        )
    return tuple(result)


def parse_individual_replay(value: Any) -> IndividualReplay:
    """Valida la respuesta individual exactamente como replay histórico v3."""
    response = _exact_object(
        value,
        required=frozenset(
            {
                "exito",
                "tipo_comprobante",
                "punto_venta",
                "numero",
                "fecha",
                "total",
                "mensaje",
            }
        ),
        optional=frozenset(
            {
                "comprobante_id",
                "cae",
                "cae_vencimiento",
                "errores",
                "errores_arca",
                "requiere_reconciliacion",
                "categoria_error",
            }
        ),
    )
    expiration = response.get("cae_vencimiento")
    return IndividualReplay(
        exito=_replay_bool(response["exito"]),
        comprobante_id=_replay_optional_int(response.get("comprobante_id")),
        tipo_comprobante=_replay_int(response["tipo_comprobante"]),
        punto_venta=_replay_int(response["punto_venta"]),
        numero=_replay_int(response["numero"]),
        fecha=_replay_date(response["fecha"]),
        cae=_replay_optional_string(response.get("cae")),
        cae_vencimiento=None if expiration is None else _replay_date(expiration),
        total=_replay_decimal(response["total"]),
        mensaje=_replay_string(response["mensaje"]),
        errores=_replay_errors(response.get("errores", [])),
        errores_arca=_replay_arca_errors(response.get("errores_arca", [])),
        requiere_reconciliacion=_replay_bool(
            response.get("requiere_reconciliacion", False)
        ),
        categoria_error=_replay_optional_string(response.get("categoria_error")),
    )


_BATCH_LOT_REQUIRED = frozenset(
    {
        "id",
        "nombre_archivo",
        "archivo_hash",
        "estado",
        "modo_procesamiento",
        "procesamiento_async",
        "total_filas",
        "total_grupos",
        "grupos_validos",
        "grupos_con_error",
        "grupos_emitidos",
        "grupos_fallidos",
        "created_at",
        "updated_at",
        "empresa_id",
    }
)
_BATCH_LOT_OPTIONAL = frozenset(
    {
        "grupos_reconciliados_externos",
        "grupos_descartados",
        "mensaje_resumen",
        "metadata_json",
        "mapeo_usado_json",
        "headers_detectados_json",
        "started_at",
        "finished_at",
        "compactado_at",
        "usuario_id",
        "formato_importacion_id",
        "formato_importacion_version_id",
    }
)


def _parse_batch_lot(value: Any) -> BatchLotReplay:
    lot = _exact_object(
        value,
        required=_BATCH_LOT_REQUIRED,
        optional=_BATCH_LOT_OPTIONAL,
    )
    for field_name in (
        "id",
        "total_filas",
        "total_grupos",
        "grupos_validos",
        "grupos_con_error",
        "grupos_emitidos",
        "grupos_fallidos",
        "empresa_id",
    ):
        _replay_int(lot[field_name])
    for field_name in ("grupos_reconciliados_externos", "grupos_descartados"):
        _replay_int(lot.get(field_name, 0))
    for field_name in (
        "nombre_archivo",
        "archivo_hash",
        "estado",
        "modo_procesamiento",
    ):
        _replay_string(lot[field_name])
    _replay_bool(lot["procesamiento_async"])
    for field_name in ("created_at", "updated_at"):
        _replay_datetime(lot[field_name])
    for field_name in ("started_at", "finished_at", "compactado_at"):
        if lot.get(field_name) is not None:
            _replay_datetime(lot[field_name])
    for field_name in (
        "usuario_id",
        "formato_importacion_id",
        "formato_importacion_version_id",
    ):
        _replay_optional_int(lot.get(field_name))
    if lot.get("mensaje_resumen") is not None:
        _replay_string(lot["mensaje_resumen"])
    for field_name in ("metadata_json", "mapeo_usado_json"):
        if lot.get(field_name) is not None and not isinstance(lot[field_name], dict):
            raise ValueError("objeto JSON de lote v3 inválido")
    headers = lot.get("headers_detectados_json")
    if headers is not None and (
        not isinstance(headers, list)
        or not all(isinstance(header, str) for header in headers)
    ):
        raise ValueError("headers de lote v3 inválidos")
    return BatchLotReplay(
        id=_replay_int(lot["id"]),
        estado=_replay_string(lot["estado"]),
        empresa_id=_replay_int(lot["empresa_id"]),
    )


def parse_batch_replay(value: Any, *, operation_type: str) -> BatchReplay:
    """Valida la respuesta batch histórica sin depender de DTOs vigentes."""
    if operation_type == "procesar_lote":
        required = frozenset({"lote", "mensaje", "en_progreso"})
        optional = frozenset({"errores_arca"})
    elif operation_type == "reintentar_fallidos_lote":
        required = frozenset({"lote", "mensaje"})
        optional = frozenset({"errores_arca"})
    else:
        raise ValueError("tipo de operación batch v3 inválido")
    response = _exact_object(value, required=required, optional=optional)
    return BatchReplay(
        lote=_parse_batch_lot(response["lote"]),
        mensaje=_replay_string(response["mensaje"]),
        en_progreso=(
            _replay_bool(response["en_progreso"])
            if operation_type == "procesar_lote"
            else None
        ),
        errores_arca=_replay_arca_errors(response.get("errores_arca", [])),
    )


def parse_batch_error_replay(value: Any) -> BatchErrorReplay:
    """Valida el replay de error batch histórico y prohíbe extensiones futuras."""
    response = _exact_object(
        value,
        required=frozenset({"categoria_error"}),
        optional=frozenset({"mensaje", "errores", "status_code"}),
    )
    raw_errors = response.get("errores")
    return BatchErrorReplay(
        categoria_error=_replay_string(response["categoria_error"]),
        mensaje=_replay_optional_string(response.get("mensaje")),
        errores=None if raw_errors is None else _replay_errors(raw_errors),
        status_code=_replay_optional_int(response.get("status_code")),
    )


def adapt_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    """Convierte una fila v3 y agrega sólo los null PF-13 autorizados."""
    columns = V3_COLUMNS[table_name]
    if set(row) != set(columns):
        raise ValueError("columnas históricas inválidas")
    converted = {
        name: validate_value(spec, row[name]) for name, spec in columns.items()
    }
    converted.update({name: None for name in TARGET_NULL_ADDITIONS.get(table_name, ())})
    return converted


def coordinator_plan(company_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Plan determinista; ``updated_at`` lo aporta la transacción de importación."""
    ids = sorted(int(row["id"]) for row in company_rows)
    return [
        {"empresa_id": company_id, "ambiente": environment, "revision": 0}
        for company_id in ids
        for environment in ("homologacion", "produccion")
    ]
