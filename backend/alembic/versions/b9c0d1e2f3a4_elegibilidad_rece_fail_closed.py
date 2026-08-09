"""elegibilidad_rece_fail_closed

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-08-08
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REVISION_ANTERIOR = "a8b9c0d1e2f3"
AMBIENTES_SQL = "'homologacion', 'produccion'"
ESTADOS_SQL = "'verificado_rece', 'no_rece', 'no_verificado'"
FUENTES_SQL = (
    "'migracion_legacy', 'alta_manual', 'sincronizacion_wsfe', "
    "'constancia_arca_atestada', 'edicion'"
)
EVIDENCIAS_SQL = "'sin_evidencia', 'rece_aplicativo_web_services_v1'"
FASES_GUARDA_SQL = (
    "'pre_arca', 'arca_iniciada', 'requiere_reconciliacion', "
    "'cerrada_pre_arca', 'cerrada_terminal'"
)
PREDICADO_GUARDA_ACTIVA = (
    "fase IN ('pre_arca', 'arca_iniciada', 'requiere_reconciliacion')"
)
NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _contar(query: str) -> int:
    """Ejecuta un conteo de preflight sin exponer filas fiscales."""
    value = op.get_bind().execute(sa.text(query)).scalar_one()
    return int(value)


def _quote_identificador_sqlite(value: str) -> str:
    """Escapa un identificador obtenido del propio catálogo SQLite."""
    return '"' + value.replace('"', '""') + '"'


def _digest_valor_sqlite(value: object) -> bytes:
    """Codifica un valor SQLite sin ambigüedad ni exposición en mensajes."""
    if value is None:
        return b"N"
    if isinstance(value, bytes):
        payload = value
        prefix = b"B"
    elif isinstance(value, str):
        payload = value.encode("utf-8")
        prefix = b"S"
    elif isinstance(value, int):
        payload = str(value).encode("ascii")
        prefix = b"I"
    elif isinstance(value, float):
        payload = value.hex().encode("ascii")
        prefix = b"F"
    else:
        payload = repr(value).encode("utf-8")
        prefix = b"R"
    return prefix + str(len(payload)).encode("ascii") + b":" + payload


def _digest_fila_sqlite(row: Sequence[object]) -> bytes:
    """Calcula una huella estable de una fila SQLite."""
    digest = hashlib.sha256()
    digest.update(str(len(row)).encode("ascii"))
    for value in row:
        encoded = _digest_valor_sqlite(value)
        digest.update(str(len(encoded)).encode("ascii"))
        digest.update(b":")
        digest.update(encoded)
    return digest.digest()


def _digest_semantico_sqlite(
    fetchall: Callable[[str], list[tuple[object, ...]]],
) -> str:
    """Resume esquema y contenido de todas las tablas sin revelar sus filas."""
    catalogo = fetchall(
        "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    )
    digest = hashlib.sha256()
    for entry in catalogo:
        digest.update(_digest_fila_sqlite(entry))

    tablas = sorted(str(row[1]) for row in catalogo if row[0] == "table")
    for tabla in tablas:
        digest.update(_digest_valor_sqlite(tabla))
        identifier = _quote_identificador_sqlite(tabla)
        columnas = fetchall(f"PRAGMA table_info({identifier})")
        digest.update(str(len(columnas)).encode("ascii"))
        for columna in columnas:
            digest.update(_digest_fila_sqlite(columna))
        row_digests = sorted(
            _digest_fila_sqlite(row) for row in fetchall(f"SELECT * FROM {identifier}")
        )
        digest.update(str(len(row_digests)).encode("ascii"))
        for row_digest in row_digests:
            digest.update(row_digest)
    return digest.hexdigest()


def _filas_bind_sqlite(query: str) -> list[tuple[object, ...]]:
    """Materializa filas de la base activa para el digest pre-DDL."""
    return [tuple(row) for row in op.get_bind().execute(sa.text(query)).fetchall()]


def _filas_backup_sqlite(
    conn: sqlite3.Connection,
) -> Callable[[str], list[tuple[object, ...]]]:
    """Adapta una conexión de backup al calculador de digest canónico."""

    def fetchall(query: str) -> list[tuple[object, ...]]:
        return [tuple(row) for row in conn.execute(query).fetchall()]

    return fetchall


def _verificar_backup_sqlite() -> None:
    """Exige y valida un backup restaurable antes de DDL SQLite no atómico."""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    if os.getenv("PF19B_SQLITE_BACKUP_CONFIRMED") != "1":
        raise RuntimeError(
            "PF-19B abortó antes del DDL SQLite: confirmá un backup con "
            "PF19B_SQLITE_BACKUP_CONFIRMED=1 y PF19B_SQLITE_BACKUP_PATH. "
            "SQLite no ofrece rollback DDL confiable bajo este Alembic."
        )

    backup_value = (os.getenv("PF19B_SQLITE_BACKUP_PATH") or "").strip()
    database_value = str(bind.engine.url.database or "").strip()
    if not backup_value or not database_value or database_value == ":memory:":
        raise RuntimeError(
            "PF-19B requiere rutas físicas de base y backup SQLite antes del DDL."
        )

    database_path = Path(database_value).resolve()
    backup_path = Path(backup_value).resolve()
    if database_path == backup_path:
        raise RuntimeError("El backup PF-19B debe ser distinto de la base activa.")
    if not backup_path.is_file() or backup_path.stat().st_size <= 0:
        raise RuntimeError("El backup SQLite PF-19B no existe o está vacío.")

    source_quick_check = bind.execute(sa.text("PRAGMA quick_check")).fetchone()
    source_fk_error = bind.execute(sa.text("PRAGMA foreign_key_check")).fetchone()
    if source_quick_check != ("ok",) or source_fk_error is not None:
        raise RuntimeError(
            "La base SQLite activa no supera quick_check/foreign_key_check pre-DDL."
        )
    source_digest_before = _digest_semantico_sqlite(_filas_bind_sqlite)
    uri = f"file:{backup_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as backup_conn:
        quick_check = backup_conn.execute("PRAGMA quick_check").fetchone()
        if quick_check != ("ok",):
            raise RuntimeError("El backup SQLite PF-19B no supera PRAGMA quick_check.")
        if backup_conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError(
                "El backup SQLite PF-19B no supera PRAGMA foreign_key_check."
            )
        backup_digest = _digest_semantico_sqlite(_filas_backup_sqlite(backup_conn))

    source_digest_after = _digest_semantico_sqlite(_filas_bind_sqlite)
    if source_digest_before != source_digest_after:
        raise RuntimeError(
            "La base SQLite cambió durante la validación del backup; "
            "detené escrituras y generá una copia nueva."
        )
    if backup_digest != source_digest_after:
        raise RuntimeError(
            "El backup SQLite PF-19B no tiene equivalencia semántica exacta "
            "de esquema y contenido con la base activa."
        )


def _verificar_datos_legacy() -> None:
    """Aborta antes del primer DDL si el ownership legacy es ambiguo."""
    conflictos = {
        "puntos_invalidos_o_huerfanos": _contar(
            "SELECT COUNT(*) FROM puntos_venta pv "
            "LEFT JOIN empresas e ON e.id = pv.empresa_id "
            "WHERE e.id IS NULL OR pv.numero < 1 OR pv.numero > 99999"
        ),
        "operaciones_lote_cruzado": _contar(
            "SELECT COUNT(*) FROM operaciones_idempotentes o "
            "LEFT JOIN empresas e ON e.id = o.empresa_id "
            "LEFT JOIN lotes_comprobantes l ON l.id = o.lote_id "
            "WHERE e.id IS NULL OR (o.lote_id IS NOT NULL "
            "AND (l.id IS NULL OR l.empresa_id <> o.empresa_id))"
        ),
        "grupos_lote_huerfano": _contar(
            "SELECT COUNT(*) FROM lotes_comprobantes_grupos g "
            "LEFT JOIN lotes_comprobantes l ON l.id = g.lote_id "
            "WHERE l.id IS NULL"
        ),
        "intentos_punto_cruzado": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal i "
            "LEFT JOIN puntos_venta pv ON pv.id = i.punto_venta_id "
            "WHERE pv.id IS NULL OR pv.empresa_id <> i.empresa_id"
        ),
        "intentos_operacion_cruzada": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal i "
            "LEFT JOIN operaciones_idempotentes o ON o.id = i.operacion_id "
            "WHERE i.operacion_id IS NOT NULL "
            "AND (o.id IS NULL OR o.empresa_id <> i.empresa_id)"
        ),
        "intentos_lote_cruzado": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal i "
            "LEFT JOIN lotes_comprobantes l ON l.id = i.lote_id "
            "WHERE i.lote_id IS NOT NULL "
            "AND (l.id IS NULL OR l.empresa_id <> i.empresa_id)"
        ),
        "intentos_grupo_cruzado": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal i "
            "LEFT JOIN lotes_comprobantes_grupos g ON g.id = i.grupo_id "
            "LEFT JOIN lotes_comprobantes l ON l.id = g.lote_id "
            "WHERE i.grupo_id IS NOT NULL AND (g.id IS NULL OR l.id IS NULL "
            "OR l.empresa_id <> i.empresa_id "
            "OR (i.lote_id IS NOT NULL AND g.lote_id <> i.lote_id))"
        ),
        "intentos_lote_grupo_incompleto": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal "
            "WHERE (lote_id IS NULL AND grupo_id IS NOT NULL) "
            "OR (lote_id IS NOT NULL AND grupo_id IS NULL)"
        ),
    }
    activos = [
        f"{categoria}={cantidad}"
        for categoria, cantidad in conflictos.items()
        if cantidad > 0
    ]
    if activos:
        raise RuntimeError(
            "PF-19B abortó antes de modificar el esquema por datos legacy "
            "incompatibles con el aislamiento fiscal: " + ", ".join(activos) + "."
        )


def _agregar_columnas_e_indices_padre() -> None:
    """Agrega revisión/snapshot y claves compuestas referenciables."""
    op.add_column(
        "puntos_venta",
        sa.Column(
            "revision_fiscal",
            sa.Integer(),
            sa.CheckConstraint(
                "revision_fiscal > 0",
                name="ck_puntos_venta_revision_fiscal_positiva",
            ),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_index(
        "uq_puntos_venta_id_empresa",
        "puntos_venta",
        ["id", "empresa_id"],
        unique=True,
    )

    op.add_column(
        "operaciones_idempotentes",
        sa.Column(
            "rece_snapshot_hash",
            sa.String(length=64),
            sa.CheckConstraint(
                "rece_snapshot_hash IS NULL OR length(rece_snapshot_hash) = 64",
                name="ck_operaciones_idempotentes_rece_snapshot_hash",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_operaciones_idempotentes_id_empresa",
        "operaciones_idempotentes",
        ["id", "empresa_id"],
        unique=True,
    )
    op.create_index(
        "uq_lotes_comprobantes_id_empresa",
        "lotes_comprobantes",
        ["id", "empresa_id"],
        unique=True,
    )

    op.add_column(
        "lotes_comprobantes_grupos",
        sa.Column(
            "empresa_id",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE lotes_comprobantes_grupos SET empresa_id = "
            "(SELECT l.empresa_id FROM lotes_comprobantes l "
            "WHERE l.id = lotes_comprobantes_grupos.lote_id)"
        )
    )
    if _contar("SELECT COUNT(*) FROM lotes_comprobantes_grupos WHERE empresa_id <= 0"):
        raise RuntimeError("PF-19B no pudo backfillear empresa_id en grupos.")
    op.create_index(
        "uq_lotes_comprobantes_grupos_id_empresa",
        "lotes_comprobantes_grupos",
        ["id", "empresa_id"],
        unique=True,
    )
    for columna in (
        sa.Column("punto_venta_id", sa.Integer(), nullable=True),
        sa.Column("ambiente", sa.String(length=20), nullable=True),
        sa.Column(
            "punto_venta_elegibilidad_revision_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("punto_venta_revision_fiscal", sa.Integer(), nullable=True),
    ):
        op.add_column("lotes_comprobantes_grupos", columna)


def _crear_ledger_y_cabezas() -> None:
    """Crea el historial inmutable y su cabeza transaccional."""
    op.create_table(
        "puntos_venta_elegibilidad_rece_revisiones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("punto_venta_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("fuente", sa.String(length=40), nullable=False),
        sa.Column("evidencia_tipo", sa.String(length=50), nullable=False),
        sa.Column("evidencia_sha256", sa.String(length=64), nullable=True),
        sa.Column("clasificador_version", sa.String(length=40), nullable=True),
        sa.Column("empresa_cuit_snapshot", sa.String(length=11), nullable=True),
        sa.Column("punto_venta_numero_snapshot", sa.Integer(), nullable=True),
        sa.Column("punto_revision_fiscal", sa.Integer(), nullable=False),
        sa.Column("documento_emitido_en", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column("observado_en", sa.DateTime(), nullable=False),
        sa.Column("verificado_en", sa.DateTime(), nullable=True),
        sa.Column("creado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("actor_usuario_id_snapshot", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            f"ambiente IN ({AMBIENTES_SQL})", name="ck_pv_rece_revision_ambiente"
        ),
        sa.CheckConstraint(
            f"estado IN ({ESTADOS_SQL})", name="ck_pv_rece_revision_estado"
        ),
        sa.CheckConstraint(
            f"fuente IN ({FUENTES_SQL})", name="ck_pv_rece_revision_fuente"
        ),
        sa.CheckConstraint(
            f"evidencia_tipo IN ({EVIDENCIAS_SQL})",
            name="ck_pv_rece_revision_evidencia_tipo",
        ),
        sa.CheckConstraint("revision > 0", name="ck_pv_rece_revision_positiva"),
        sa.CheckConstraint(
            "punto_revision_fiscal > 0",
            name="ck_pv_rece_revision_fiscal_positiva",
        ),
        sa.CheckConstraint(
            "evidencia_sha256 IS NULL OR length(evidencia_sha256) = 64",
            name="ck_pv_rece_revision_sha256",
        ),
        sa.CheckConstraint(
            "empresa_cuit_snapshot IS NULL OR length(empresa_cuit_snapshot) = 11",
            name="ck_pv_rece_revision_cuit_snapshot",
        ),
        sa.CheckConstraint(
            "punto_venta_numero_snapshot IS NULL OR "
            "punto_venta_numero_snapshot BETWEEN 1 AND 99999",
            name="ck_pv_rece_revision_numero_snapshot",
        ),
        sa.CheckConstraint(
            "actor_usuario_id_snapshot IS NULL OR actor_usuario_id_snapshot > 0",
            name="ck_pv_rece_revision_actor_snapshot",
        ),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR documento_emitido_en IS NULL OR "
            "vigente_hasta >= documento_emitido_en",
            name="ck_pv_rece_revision_vigencia",
        ),
        sa.CheckConstraint(
            "((estado = 'verificado_rece' "
            "AND ambiente = 'produccion' "
            "AND fuente = 'constancia_arca_atestada' "
            "AND evidencia_tipo = 'rece_aplicativo_web_services_v1' "
            "AND evidencia_sha256 IS NOT NULL "
            "AND clasificador_version IS NOT NULL "
            "AND empresa_cuit_snapshot IS NOT NULL "
            "AND punto_venta_numero_snapshot IS NOT NULL "
            "AND documento_emitido_en IS NOT NULL "
            "AND vigente_hasta IS NOT NULL "
            "AND verificado_en IS NOT NULL "
            "AND actor_usuario_id_snapshot IS NOT NULL) "
            "OR (estado <> 'verificado_rece' AND vigente_hasta IS NULL "
            "AND verificado_en IS NULL))",
            name="ck_pv_rece_revision_verificada_coherente",
        ),
        sa.CheckConstraint(
            "fuente NOT IN ('migracion_legacy', 'alta_manual', "
            "'sincronizacion_wsfe', 'edicion') OR estado <> 'verificado_rece'",
            name="ck_pv_rece_revision_fuente_no_promueve",
        ),
        sa.ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_pv_rece_revision_punto_empresa",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_usuario_id"],
            ["usuarios.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "punto_venta_id",
            "ambiente",
            "revision",
            name="uq_pv_rece_revision_punto_ambiente_revision",
        ),
        sa.UniqueConstraint(
            "id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            name="uq_pv_rece_revision_identidad_compuesta",
        ),
    )
    op.create_index(
        op.f("ix_puntos_venta_elegibilidad_rece_revisiones_id"),
        "puntos_venta_elegibilidad_rece_revisiones",
        ["id"],
    )

    op.create_table(
        "puntos_venta_elegibilidad_rece_actual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("punto_venta_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("revision_actual_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            f"ambiente IN ({AMBIENTES_SQL})", name="ck_pv_rece_actual_ambiente"
        ),
        sa.ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_pv_rece_actual_punto_empresa",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revision_actual_id", "empresa_id", "punto_venta_id", "ambiente"],
            [
                "puntos_venta_elegibilidad_rece_revisiones.id",
                "puntos_venta_elegibilidad_rece_revisiones.empresa_id",
                "puntos_venta_elegibilidad_rece_revisiones.punto_venta_id",
                "puntos_venta_elegibilidad_rece_revisiones.ambiente",
            ],
            name="fk_pv_rece_actual_revision_compuesta",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "punto_venta_id",
            "ambiente",
            name="uq_pv_rece_actual_punto_ambiente",
        ),
    )
    op.create_index(
        op.f("ix_puntos_venta_elegibilidad_rece_actual_id"),
        "puntos_venta_elegibilidad_rece_actual",
        ["id"],
    )


def _backfill_ledger() -> None:
    """Crea dos revisiones cerradas por cada punto legacy."""
    bind = op.get_bind()
    metadata = sa.MetaData()
    revisiones = sa.Table(
        "puntos_venta_elegibilidad_rece_revisiones",
        metadata,
        autoload_with=bind,
    )
    cabezas = sa.Table(
        "puntos_venta_elegibilidad_rece_actual",
        metadata,
        autoload_with=bind,
    )
    puntos = bind.execute(
        sa.text("SELECT id, empresa_id, revision_fiscal FROM puntos_venta ORDER BY id")
    ).mappings()
    ahora = datetime.utcnow()
    for punto in puntos:
        for ambiente in ("homologacion", "produccion"):
            resultado = bind.execute(
                revisiones.insert().values(
                    empresa_id=punto["empresa_id"],
                    punto_venta_id=punto["id"],
                    ambiente=ambiente,
                    revision=1,
                    estado="no_verificado",
                    fuente="migracion_legacy",
                    evidencia_tipo="sin_evidencia",
                    punto_revision_fiscal=punto["revision_fiscal"],
                    observado_en=ahora,
                    created_at=ahora,
                )
            )
            revision_id = int(resultado.inserted_primary_key[0])
            bind.execute(
                cabezas.insert().values(
                    empresa_id=punto["empresa_id"],
                    punto_venta_id=punto["id"],
                    ambiente=ambiente,
                    revision_actual_id=revision_id,
                    created_at=ahora,
                    updated_at=ahora,
                )
            )


def _crear_asociaciones_y_guardas() -> None:
    """Crea snapshots de operación y guardas durables previas a FECAE."""
    op.create_table(
        "operaciones_idempotentes_elegibilidad_rece",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operacion_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("punto_venta_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("elegibilidad_revision_id", sa.Integer(), nullable=False),
        sa.Column("punto_venta_revision_fiscal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            f"ambiente IN ({AMBIENTES_SQL})", name="ck_operacion_rece_ambiente"
        ),
        sa.CheckConstraint(
            "punto_venta_revision_fiscal > 0",
            name="ck_operacion_rece_revision_fiscal_positiva",
        ),
        sa.ForeignKeyConstraint(
            ["operacion_id", "empresa_id"],
            ["operaciones_idempotentes.id", "operaciones_idempotentes.empresa_id"],
            name="fk_operacion_rece_operacion_empresa",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_operacion_rece_punto_empresa",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["elegibilidad_revision_id", "empresa_id", "punto_venta_id", "ambiente"],
            [
                "puntos_venta_elegibilidad_rece_revisiones.id",
                "puntos_venta_elegibilidad_rece_revisiones.empresa_id",
                "puntos_venta_elegibilidad_rece_revisiones.punto_venta_id",
                "puntos_venta_elegibilidad_rece_revisiones.ambiente",
            ],
            name="fk_operacion_rece_revision_compuesta",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operacion_id",
            "punto_venta_id",
            "ambiente",
            name="uq_operacion_rece_punto_ambiente",
        ),
        sa.UniqueConstraint(
            "operacion_id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            name="uq_operacion_rece_snapshot_compuesto",
        ),
    )
    op.create_index(
        op.f("ix_operaciones_idempotentes_elegibilidad_rece_id"),
        "operaciones_idempotentes_elegibilidad_rece",
        ["id"],
    )

    op.create_table(
        "puntos_venta_guardas_emision_rece",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("fase", sa.String(length=40), nullable=False),
        sa.Column("operacion_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("punto_venta_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("elegibilidad_revision_id", sa.Integer(), nullable=False),
        sa.Column("punto_venta_revision_fiscal", sa.Integer(), nullable=False),
        sa.Column("arca_iniciada_en", sa.DateTime(), nullable=True),
        sa.Column("cerrada_en", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            f"ambiente IN ({AMBIENTES_SQL})", name="ck_guarda_rece_ambiente"
        ),
        sa.CheckConstraint(f"fase IN ({FASES_GUARDA_SQL})", name="ck_guarda_rece_fase"),
        sa.CheckConstraint(
            "punto_venta_revision_fiscal > 0",
            name="ck_guarda_rece_revision_fiscal_positiva",
        ),
        sa.CheckConstraint(
            "((fase = 'pre_arca' AND arca_iniciada_en IS NULL "
            "AND cerrada_en IS NULL) "
            "OR (fase IN ('arca_iniciada', 'requiere_reconciliacion') "
            "AND arca_iniciada_en IS NOT NULL AND cerrada_en IS NULL) "
            "OR (fase = 'cerrada_pre_arca' AND arca_iniciada_en IS NULL "
            "AND cerrada_en IS NOT NULL) "
            "OR (fase = 'cerrada_terminal' AND arca_iniciada_en IS NOT NULL "
            "AND cerrada_en IS NOT NULL))",
            name="ck_guarda_rece_fase_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["operacion_id", "empresa_id"],
            ["operaciones_idempotentes.id", "operaciones_idempotentes.empresa_id"],
            name="fk_guarda_rece_operacion_empresa",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["punto_venta_id", "empresa_id"],
            ["puntos_venta.id", "puntos_venta.empresa_id"],
            name="fk_guarda_rece_punto_empresa",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["elegibilidad_revision_id", "empresa_id", "punto_venta_id", "ambiente"],
            [
                "puntos_venta_elegibilidad_rece_revisiones.id",
                "puntos_venta_elegibilidad_rece_revisiones.empresa_id",
                "puntos_venta_elegibilidad_rece_revisiones.punto_venta_id",
                "puntos_venta_elegibilidad_rece_revisiones.ambiente",
            ],
            name="fk_guarda_rece_revision_compuesta",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ],
            [
                "operaciones_idempotentes_elegibilidad_rece.operacion_id",
                "operaciones_idempotentes_elegibilidad_rece.empresa_id",
                "operaciones_idempotentes_elegibilidad_rece.punto_venta_id",
                "operaciones_idempotentes_elegibilidad_rece.ambiente",
                "operaciones_idempotentes_elegibilidad_rece.elegibilidad_revision_id",
                "operaciones_idempotentes_elegibilidad_rece.punto_venta_revision_fiscal",
            ],
            name="fk_guarda_rece_snapshot_operacion",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_guarda_rece_token"),
        sa.UniqueConstraint(
            "id",
            "operacion_id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            name="uq_guarda_rece_identidad_compuesta",
        ),
    )
    op.create_index(
        op.f("ix_puntos_venta_guardas_emision_rece_id"),
        "puntos_venta_guardas_emision_rece",
        ["id"],
    )
    op.create_index(
        "ix_guarda_rece_operacion",
        "puntos_venta_guardas_emision_rece",
        ["operacion_id", "fase"],
    )
    op.create_index(
        "uq_guarda_rece_activa",
        "puntos_venta_guardas_emision_rece",
        ["empresa_id", "punto_venta_id", "ambiente"],
        unique=True,
        sqlite_where=sa.text(PREDICADO_GUARDA_ACTIVA),
        postgresql_where=sa.text(PREDICADO_GUARDA_ACTIVA),
    )


def _nombre_fk_simple(
    table_name: str,
    column_name: str,
    referred_table: str,
) -> str:
    """Resuelve una FK legacy aun cuando SQLite la refleje sin nombre."""
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if (
            foreign_key.get("constrained_columns") == [column_name]
            and foreign_key.get("referred_table") == referred_table
        ):
            name = foreign_key.get("name")
            if name:
                return str(name)
    return f"fk_{table_name}_{column_name}_{referred_table}"


def _reemplazar_fk_simple_intento(
    column_name: str,
    referred_table: str,
    *,
    ondelete: str,
) -> None:
    """Alinea la FK simple legacy con las nuevas garantías compuestas."""
    fk_name = _nombre_fk_simple(
        "intentos_emision_fiscal",
        column_name,
        referred_table,
    )
    with op.batch_alter_table(
        "intentos_emision_fiscal",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            fk_name,
            referred_table,
            [column_name],
            ["id"],
            ondelete=ondelete,
        )


def _agregar_snapshots_hijos() -> None:
    """Agrega snapshots nulos legacy y constraints compuestos a grupos/intentos."""
    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        batch_op.create_unique_constraint(
            "uq_lotes_grupos_identidad_fiscal_compuesta",
            [
                "id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ],
        )
        batch_op.create_check_constraint(
            "ck_lotes_grupos_snapshot_rece_completo",
            "((punto_venta_id IS NULL AND ambiente IS NULL "
            "AND punto_venta_elegibilidad_revision_id IS NULL "
            "AND punto_venta_revision_fiscal IS NULL) "
            "OR (punto_venta_id IS NOT NULL "
            "AND punto_venta_numero IS NOT NULL "
            "AND tipo_comprobante IS NOT NULL "
            "AND ambiente IS NOT NULL "
            "AND ambiente IN ('homologacion', 'produccion') "
            "AND punto_venta_elegibilidad_revision_id IS NOT NULL "
            "AND punto_venta_revision_fiscal IS NOT NULL "
            "AND punto_venta_revision_fiscal > 0))",
        )
        batch_op.create_foreign_key(
            "fk_lotes_grupos_lote_empresa",
            "lotes_comprobantes",
            ["lote_id", "empresa_id"],
            ["id", "empresa_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_lotes_grupos_punto_empresa",
            "puntos_venta",
            ["punto_venta_id", "empresa_id"],
            ["id", "empresa_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_lotes_grupos_revision_rece_compuesta",
            "puntos_venta_elegibilidad_rece_revisiones",
            [
                "punto_venta_elegibilidad_revision_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
            ],
            ["id", "empresa_id", "punto_venta_id", "ambiente"],
            ondelete="RESTRICT",
        )

    for columna in (
        sa.Column("ambiente", sa.String(length=20), nullable=True),
        sa.Column("punto_venta_elegibilidad_revision_id", sa.Integer(), nullable=True),
        sa.Column("punto_venta_revision_fiscal", sa.Integer(), nullable=True),
        sa.Column("guarda_rece_id", sa.Integer(), nullable=True),
    ):
        op.add_column("intentos_emision_fiscal", columna)

    _reemplazar_fk_simple_intento(
        "lote_id",
        "lotes_comprobantes",
        ondelete="RESTRICT",
    )
    _reemplazar_fk_simple_intento(
        "grupo_id",
        "lotes_comprobantes_grupos",
        ondelete="RESTRICT",
    )

    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.create_check_constraint(
            "ck_intentos_emision_fiscal_snapshot_rece_completo",
            "(((lote_id IS NULL AND grupo_id IS NULL) "
            "OR (lote_id IS NOT NULL AND grupo_id IS NOT NULL)) "
            "AND ((ambiente IS NULL "
            "AND punto_venta_elegibilidad_revision_id IS NULL "
            "AND punto_venta_revision_fiscal IS NULL "
            "AND guarda_rece_id IS NULL) "
            "OR (ambiente IS NOT NULL "
            "AND ambiente IN ('homologacion', 'produccion') "
            "AND operacion_id IS NOT NULL "
            "AND punto_venta_elegibilidad_revision_id IS NOT NULL "
            "AND punto_venta_revision_fiscal IS NOT NULL "
            "AND punto_venta_revision_fiscal > 0 "
            "AND guarda_rece_id IS NOT NULL)))",
        )
        batch_op.create_foreign_key(
            "fk_intento_operacion_empresa",
            "operaciones_idempotentes",
            ["operacion_id", "empresa_id"],
            ["id", "empresa_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_intento_punto_empresa",
            "puntos_venta",
            ["punto_venta_id", "empresa_id"],
            ["id", "empresa_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_intento_revision_rece_compuesta",
            "puntos_venta_elegibilidad_rece_revisiones",
            [
                "punto_venta_elegibilidad_revision_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
            ],
            ["id", "empresa_id", "punto_venta_id", "ambiente"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_intento_lote_empresa",
            "lotes_comprobantes",
            ["lote_id", "empresa_id"],
            ["id", "empresa_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_intento_grupo_empresa",
            "lotes_comprobantes_grupos",
            ["grupo_id", "empresa_id"],
            ["id", "empresa_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_intento_grupo_snapshot_rece_exacto",
            "lotes_comprobantes_grupos",
            [
                "grupo_id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ],
            [
                "id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_intento_guarda_rece_simple",
            "puntos_venta_guardas_emision_rece",
            ["guarda_rece_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_intento_guarda_rece_compuesta",
            "puntos_venta_guardas_emision_rece",
            [
                "guarda_rece_id",
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ],
            [
                "id",
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ],
            ondelete="RESTRICT",
        )


def _exigir_fk(
    inspector: sa.Inspector,
    table_name: str,
    constraint_name: str,
    constrained_columns: Sequence[str],
    referred_table: str,
    referred_columns: Sequence[str],
    ondelete: str,
) -> None:
    """Comprueba la firma completa de una FK crítica creada por PF-19B."""
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("name") != constraint_name:
            continue
        options = foreign_key.get("options") or {}
        if (
            foreign_key.get("constrained_columns") == list(constrained_columns)
            and foreign_key.get("referred_table") == referred_table
            and foreign_key.get("referred_columns") == list(referred_columns)
            and str(options.get("ondelete") or "").upper() == ondelete
        ):
            return
    raise RuntimeError(
        f"PF-19B no encontró la FK crítica {constraint_name} con su firma exacta."
    )


def _verificar_ddl_upgrade() -> None:
    """Inspecciona checks, FKs, uniques e índice parcial en la base activa."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    checks_esperados = {
        "puntos_venta": {"ck_puntos_venta_revision_fiscal_positiva"},
        "operaciones_idempotentes": {"ck_operaciones_idempotentes_rece_snapshot_hash"},
        "lotes_comprobantes_grupos": {"ck_lotes_grupos_snapshot_rece_completo"},
        "intentos_emision_fiscal": {
            "ck_intentos_emision_fiscal_snapshot_rece_completo"
        },
        "puntos_venta_elegibilidad_rece_revisiones": {
            "ck_pv_rece_revision_ambiente",
            "ck_pv_rece_revision_estado",
            "ck_pv_rece_revision_fuente",
            "ck_pv_rece_revision_evidencia_tipo",
            "ck_pv_rece_revision_positiva",
            "ck_pv_rece_revision_fiscal_positiva",
            "ck_pv_rece_revision_sha256",
            "ck_pv_rece_revision_cuit_snapshot",
            "ck_pv_rece_revision_numero_snapshot",
            "ck_pv_rece_revision_actor_snapshot",
            "ck_pv_rece_revision_vigencia",
            "ck_pv_rece_revision_verificada_coherente",
            "ck_pv_rece_revision_fuente_no_promueve",
        },
        "puntos_venta_elegibilidad_rece_actual": {"ck_pv_rece_actual_ambiente"},
        "operaciones_idempotentes_elegibilidad_rece": {
            "ck_operacion_rece_ambiente",
            "ck_operacion_rece_revision_fiscal_positiva",
        },
        "puntos_venta_guardas_emision_rece": {
            "ck_guarda_rece_ambiente",
            "ck_guarda_rece_fase",
            "ck_guarda_rece_revision_fiscal_positiva",
            "ck_guarda_rece_fase_timestamps",
        },
    }
    for table_name, expected in checks_esperados.items():
        actual = {
            item.get("name") for item in inspector.get_check_constraints(table_name)
        }
        missing = expected - actual
        if missing:
            raise RuntimeError(
                "PF-19B no materializó checks críticos en "
                f"{table_name}: {', '.join(sorted(missing))}."
            )

    fks_esperadas = (
        (
            "puntos_venta_elegibilidad_rece_revisiones",
            "fk_pv_rece_revision_punto_empresa",
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "puntos_venta_elegibilidad_rece_actual",
            "fk_pv_rece_actual_punto_empresa",
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "puntos_venta_elegibilidad_rece_actual",
            "fk_pv_rece_actual_revision_compuesta",
            ("revision_actual_id", "empresa_id", "punto_venta_id", "ambiente"),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
            "RESTRICT",
        ),
        (
            "operaciones_idempotentes_elegibilidad_rece",
            "fk_operacion_rece_operacion_empresa",
            ("operacion_id", "empresa_id"),
            "operaciones_idempotentes",
            ("id", "empresa_id"),
            "CASCADE",
        ),
        (
            "operaciones_idempotentes_elegibilidad_rece",
            "fk_operacion_rece_punto_empresa",
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "operaciones_idempotentes_elegibilidad_rece",
            "fk_operacion_rece_revision_compuesta",
            ("elegibilidad_revision_id", "empresa_id", "punto_venta_id", "ambiente"),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
            "RESTRICT",
        ),
        (
            "puntos_venta_guardas_emision_rece",
            "fk_guarda_rece_operacion_empresa",
            ("operacion_id", "empresa_id"),
            "operaciones_idempotentes",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "puntos_venta_guardas_emision_rece",
            "fk_guarda_rece_punto_empresa",
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "puntos_venta_guardas_emision_rece",
            "fk_guarda_rece_revision_compuesta",
            ("elegibilidad_revision_id", "empresa_id", "punto_venta_id", "ambiente"),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
            "RESTRICT",
        ),
        (
            "puntos_venta_guardas_emision_rece",
            "fk_guarda_rece_snapshot_operacion",
            (
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ),
            "operaciones_idempotentes_elegibilidad_rece",
            (
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ),
            "RESTRICT",
        ),
        (
            "lotes_comprobantes_grupos",
            "fk_lotes_grupos_lote_empresa",
            ("lote_id", "empresa_id"),
            "lotes_comprobantes",
            ("id", "empresa_id"),
            "CASCADE",
        ),
        (
            "lotes_comprobantes_grupos",
            "fk_lotes_grupos_punto_empresa",
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "lotes_comprobantes_grupos",
            "fk_lotes_grupos_revision_rece_compuesta",
            (
                "punto_venta_elegibilidad_revision_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
            ),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_operacion_empresa",
            ("operacion_id", "empresa_id"),
            "operaciones_idempotentes",
            ("id", "empresa_id"),
            "CASCADE",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_punto_empresa",
            ("punto_venta_id", "empresa_id"),
            "puntos_venta",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_revision_rece_compuesta",
            (
                "punto_venta_elegibilidad_revision_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
            ),
            "puntos_venta_elegibilidad_rece_revisiones",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_lote_empresa",
            ("lote_id", "empresa_id"),
            "lotes_comprobantes",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_guarda_rece_simple",
            ("guarda_rece_id",),
            "puntos_venta_guardas_emision_rece",
            ("id",),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_grupo_empresa",
            ("grupo_id", "empresa_id"),
            "lotes_comprobantes_grupos",
            ("id", "empresa_id"),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_grupo_snapshot_rece_exacto",
            (
                "grupo_id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ),
            "lotes_comprobantes_grupos",
            (
                "id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ),
            "RESTRICT",
        ),
        (
            "intentos_emision_fiscal",
            "fk_intento_guarda_rece_compuesta",
            (
                "guarda_rece_id",
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ),
            "puntos_venta_guardas_emision_rece",
            (
                "id",
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ),
            "RESTRICT",
        ),
    )
    for foreign_key in fks_esperadas:
        _exigir_fk(inspector, *foreign_key)

    for column_name, referred_table in (
        ("lote_id", "lotes_comprobantes"),
        ("grupo_id", "lotes_comprobantes_grupos"),
    ):
        fk_name = _nombre_fk_simple(
            "intentos_emision_fiscal", column_name, referred_table
        )
        _exigir_fk(
            inspector,
            "intentos_emision_fiscal",
            fk_name,
            (column_name,),
            referred_table,
            ("id",),
            "RESTRICT",
        )

    uniques_esperadas = (
        (
            "puntos_venta_elegibilidad_rece_revisiones",
            "uq_pv_rece_revision_punto_ambiente_revision",
            ("punto_venta_id", "ambiente", "revision"),
        ),
        (
            "puntos_venta_elegibilidad_rece_revisiones",
            "uq_pv_rece_revision_identidad_compuesta",
            ("id", "empresa_id", "punto_venta_id", "ambiente"),
        ),
        (
            "puntos_venta_elegibilidad_rece_actual",
            "uq_pv_rece_actual_punto_ambiente",
            ("punto_venta_id", "ambiente"),
        ),
        (
            "operaciones_idempotentes_elegibilidad_rece",
            "uq_operacion_rece_punto_ambiente",
            ("operacion_id", "punto_venta_id", "ambiente"),
        ),
        (
            "operaciones_idempotentes_elegibilidad_rece",
            "uq_operacion_rece_snapshot_compuesto",
            (
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ),
        ),
        (
            "puntos_venta_guardas_emision_rece",
            "uq_guarda_rece_token",
            ("token",),
        ),
        (
            "puntos_venta_guardas_emision_rece",
            "uq_guarda_rece_identidad_compuesta",
            (
                "id",
                "operacion_id",
                "empresa_id",
                "punto_venta_id",
                "ambiente",
                "elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
            ),
        ),
        (
            "lotes_comprobantes_grupos",
            "uq_lotes_grupos_identidad_fiscal_compuesta",
            (
                "id",
                "lote_id",
                "empresa_id",
                "punto_venta_id",
                "punto_venta_numero",
                "ambiente",
                "punto_venta_elegibilidad_revision_id",
                "punto_venta_revision_fiscal",
                "tipo_comprobante",
            ),
        ),
    )
    for table_name, constraint_name, columns in uniques_esperadas:
        matches = [
            item
            for item in inspector.get_unique_constraints(table_name)
            if item.get("name") == constraint_name
            and tuple(item.get("column_names") or ()) == columns
        ]
        if not matches:
            raise RuntimeError(
                "PF-19B no materializó el unique crítico "
                f"{constraint_name} con sus columnas exactas."
            )

    indices_requeridos = {
        ("puntos_venta", "uq_puntos_venta_id_empresa", ("id", "empresa_id")),
        (
            "operaciones_idempotentes",
            "uq_operaciones_idempotentes_id_empresa",
            ("id", "empresa_id"),
        ),
        (
            "lotes_comprobantes",
            "uq_lotes_comprobantes_id_empresa",
            ("id", "empresa_id"),
        ),
        (
            "lotes_comprobantes_grupos",
            "uq_lotes_comprobantes_grupos_id_empresa",
            ("id", "empresa_id"),
        ),
    }
    for table_name, index_name, columns in indices_requeridos:
        matches = [
            item
            for item in inspector.get_indexes(table_name)
            if item.get("name") == index_name
            and item.get("unique")
            and tuple(item.get("column_names") or ()) == columns
        ]
        if not matches:
            raise RuntimeError(
                f"PF-19B no materializó el índice único crítico {index_name}."
            )

    partial = next(
        (
            item
            for item in inspector.get_indexes("puntos_venta_guardas_emision_rece")
            if item.get("name") == "uq_guarda_rece_activa"
            and item.get("unique")
            and tuple(item.get("column_names") or ())
            == ("empresa_id", "punto_venta_id", "ambiente")
        ),
        None,
    )
    if partial is None:
        raise RuntimeError("PF-19B no materializó uq_guarda_rece_activa.")
    dialect_options = partial.get("dialect_options") or {}
    predicate_value = dialect_options.get("sqlite_where")
    if predicate_value is None:
        predicate_value = dialect_options.get("postgresql_where")
    predicate = str(predicate_value) if predicate_value is not None else ""
    if bind.dialect.name == "sqlite" and not predicate:
        predicate = str(
            bind.execute(
                sa.text(
                    "SELECT COALESCE(sql, '') FROM sqlite_schema "
                    "WHERE type = 'index' AND name = 'uq_guarda_rece_activa'"
                )
            ).scalar_one_or_none()
            or ""
        )
    if not all(
        value in predicate
        for value in (
            "fase",
            "pre_arca",
            "arca_iniciada",
            "requiere_reconciliacion",
        )
    ):
        raise RuntimeError(
            "PF-19B no materializó el predicado exacto de la guarda activa."
        )


def _verificar_upgrade() -> None:
    """Confirma datos, integridad y DDL efectivo del cierre inicial."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        if bind.execute(sa.text("PRAGMA quick_check")).fetchone() != ("ok",):
            raise RuntimeError("PF-19B falló PRAGMA quick_check post-upgrade.")
        if bind.execute(sa.text("PRAGMA foreign_key_check")).fetchone() is not None:
            raise RuntimeError("PF-19B falló PRAGMA foreign_key_check post-upgrade.")

    puntos = _contar("SELECT COUNT(*) FROM puntos_venta")
    revisiones = _contar(
        "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones"
    )
    cabezas = _contar("SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual")
    conflictos = {
        "revision_fiscal_punto": _contar(
            "SELECT COUNT(*) FROM puntos_venta WHERE revision_fiscal <> 1"
        ),
        "revision_inicial_invalida": _contar(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones "
            "WHERE revision <> 1 OR estado <> 'no_verificado' "
            "OR fuente <> 'migracion_legacy' OR evidencia_tipo <> 'sin_evidencia' "
            "OR punto_revision_fiscal <> 1 OR evidencia_sha256 IS NOT NULL "
            "OR clasificador_version IS NOT NULL OR empresa_cuit_snapshot IS NOT NULL "
            "OR punto_venta_numero_snapshot IS NOT NULL "
            "OR documento_emitido_en IS NOT NULL OR vigente_hasta IS NOT NULL "
            "OR verificado_en IS NOT NULL OR actor_usuario_id_snapshot IS NOT NULL"
        ),
        "revision_ownership": _contar(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones r "
            "LEFT JOIN puntos_venta pv ON pv.id = r.punto_venta_id "
            "WHERE pv.id IS NULL OR pv.empresa_id <> r.empresa_id"
        ),
        "cabeza_huerfana_o_cruzada": _contar(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual a "
            "LEFT JOIN puntos_venta pv ON pv.id = a.punto_venta_id "
            "LEFT JOIN puntos_venta_elegibilidad_rece_revisiones r "
            "ON r.id = a.revision_actual_id "
            "WHERE pv.id IS NULL OR pv.empresa_id <> a.empresa_id OR r.id IS NULL "
            "OR r.empresa_id <> a.empresa_id "
            "OR r.punto_venta_id <> a.punto_venta_id "
            "OR r.ambiente <> a.ambiente"
        ),
        "cabezas_no_exactas": _contar(
            "SELECT COUNT(*) FROM ("
            "SELECT pv.id FROM puntos_venta pv "
            "LEFT JOIN puntos_venta_elegibilidad_rece_actual a "
            "ON a.punto_venta_id = pv.id AND a.empresa_id = pv.empresa_id "
            "GROUP BY pv.id HAVING COUNT(a.id) <> 2 "
            "OR SUM(CASE WHEN a.ambiente = 'homologacion' THEN 1 ELSE 0 END) <> 1 "
            "OR SUM(CASE WHEN a.ambiente = 'produccion' THEN 1 ELSE 0 END) <> 1"
            ") AS puntos_invalidos"
        ),
        "grupo_ownership": _contar(
            "SELECT COUNT(*) FROM lotes_comprobantes_grupos g "
            "LEFT JOIN lotes_comprobantes l ON l.id = g.lote_id "
            "WHERE l.id IS NULL OR g.empresa_id <> l.empresa_id"
        ),
        "grupo_snapshot_inferido": _contar(
            "SELECT COUNT(*) FROM lotes_comprobantes_grupos "
            "WHERE punto_venta_id IS NOT NULL OR ambiente IS NOT NULL "
            "OR punto_venta_elegibilidad_revision_id IS NOT NULL "
            "OR punto_venta_revision_fiscal IS NOT NULL"
        ),
        "operacion_snapshot_inferido": _contar(
            "SELECT COUNT(*) FROM operaciones_idempotentes "
            "WHERE rece_snapshot_hash IS NOT NULL"
        ),
        "asociacion_inferida": _contar(
            "SELECT COUNT(*) FROM operaciones_idempotentes_elegibilidad_rece"
        ),
        "guarda_inferida": _contar(
            "SELECT COUNT(*) FROM puntos_venta_guardas_emision_rece"
        ),
        "intento_snapshot_inferido": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal "
            "WHERE ambiente IS NOT NULL "
            "OR punto_venta_elegibilidad_revision_id IS NOT NULL "
            "OR punto_venta_revision_fiscal IS NOT NULL OR guarda_rece_id IS NOT NULL"
        ),
    }
    if revisiones != puntos * 2:
        conflictos["conteo_revisiones"] = abs(revisiones - puntos * 2) or 1
    if cabezas != puntos * 2:
        conflictos["conteo_cabezas"] = abs(cabezas - puntos * 2) or 1
    activos = [
        f"{categoria}={cantidad}"
        for categoria, cantidad in conflictos.items()
        if cantidad > 0
    ]
    if activos:
        raise RuntimeError(
            "PF-19B no pudo verificar el backfill cerrado de elegibilidad RECE: "
            + ", ".join(activos)
            + ". En SQLite restaurá el backup confirmado antes de reintentar."
        )
    _verificar_ddl_upgrade()


def upgrade() -> None:
    """Instala la autoridad RECE fail-closed y snapshots fiscales durables."""
    _verificar_backup_sqlite()
    _verificar_datos_legacy()
    _agregar_columnas_e_indices_padre()
    _crear_ledger_y_cabezas()
    _backfill_ledger()
    _crear_asociaciones_y_guardas()
    _agregar_snapshots_hijos()
    _verificar_upgrade()


def _verificar_downgrade() -> None:
    """Impide retirar PF-19B después de aceptar evidencia o actividad nueva."""
    conflictos = {
        "evidencia_no_migratoria": _contar(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones "
            "WHERE fuente <> 'migracion_legacy'"
        ),
        "revision_fiscal_modificada": _contar(
            "SELECT COUNT(*) FROM puntos_venta WHERE revision_fiscal <> 1"
        ),
        "snapshots_operacion": _contar(
            "SELECT COUNT(*) FROM operaciones_idempotentes_elegibilidad_rece"
        ),
        "guardas": _contar("SELECT COUNT(*) FROM puntos_venta_guardas_emision_rece"),
        "operaciones_con_digest": _contar(
            "SELECT COUNT(*) FROM operaciones_idempotentes "
            "WHERE rece_snapshot_hash IS NOT NULL"
        ),
        "intentos_con_snapshot": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal "
            "WHERE ambiente IS NOT NULL "
            "OR punto_venta_elegibilidad_revision_id IS NOT NULL "
            "OR punto_venta_revision_fiscal IS NOT NULL OR guarda_rece_id IS NOT NULL"
        ),
        "grupos_con_snapshot": _contar(
            "SELECT COUNT(*) FROM lotes_comprobantes_grupos "
            "WHERE punto_venta_id IS NOT NULL OR ambiente IS NOT NULL "
            "OR punto_venta_elegibilidad_revision_id IS NOT NULL "
            "OR punto_venta_revision_fiscal IS NOT NULL"
        ),
    }
    puntos = _contar("SELECT COUNT(*) FROM puntos_venta")
    revisiones = _contar(
        "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones"
    )
    cabezas = _contar("SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual")
    cabezas_iniciales_invalidas = _contar(
        "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual a "
        "JOIN puntos_venta_elegibilidad_rece_revisiones r "
        "ON r.id = a.revision_actual_id "
        "WHERE r.revision <> 1 OR r.estado <> 'no_verificado' "
        "OR r.fuente <> 'migracion_legacy' "
        "OR r.empresa_id <> a.empresa_id "
        "OR r.punto_venta_id <> a.punto_venta_id "
        "OR r.ambiente <> a.ambiente"
    )
    if revisiones != puntos * 2 or cabezas != puntos * 2:
        conflictos["conteos_ledger"] = 1
    if cabezas_iniciales_invalidas:
        conflictos["cabezas_no_iniciales"] = cabezas_iniciales_invalidas
    activos = [
        f"{categoria}={cantidad}"
        for categoria, cantidad in conflictos.items()
        if cantidad > 0
    ]
    if activos:
        raise RuntimeError(
            "PF-19B bloqueó el downgrade para no eliminar evidencia o snapshots: "
            + ", ".join(activos)
            + "."
        )


def _verificar_downgrade_aplicado() -> None:
    """Comprueba que el teardown restauró esquema e integridad legacy."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tablas_retiradas = {
        "puntos_venta_elegibilidad_rece_revisiones",
        "puntos_venta_elegibilidad_rece_actual",
        "operaciones_idempotentes_elegibilidad_rece",
        "puntos_venta_guardas_emision_rece",
    }
    presentes = tablas_retiradas & set(inspector.get_table_names())
    if presentes:
        raise RuntimeError(
            "PF-19B dejó tablas residuales tras downgrade: "
            + ", ".join(sorted(presentes))
            + "."
        )
    columnas_retiradas = {
        "puntos_venta": {"revision_fiscal"},
        "operaciones_idempotentes": {"rece_snapshot_hash"},
        "lotes_comprobantes_grupos": {
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "punto_venta_elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
        },
        "intentos_emision_fiscal": {
            "ambiente",
            "punto_venta_elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            "guarda_rece_id",
        },
    }
    for table_name, forbidden in columnas_retiradas.items():
        actual = {str(column["name"]) for column in inspector.get_columns(table_name)}
        residual = forbidden & actual
        if residual:
            raise RuntimeError(
                f"PF-19B dejó columnas residuales en {table_name}: "
                + ", ".join(sorted(residual))
                + "."
            )
    for column_name, referred_table in (
        ("lote_id", "lotes_comprobantes"),
        ("grupo_id", "lotes_comprobantes_grupos"),
    ):
        fk_name = _nombre_fk_simple(
            "intentos_emision_fiscal", column_name, referred_table
        )
        _exigir_fk(
            inspector,
            "intentos_emision_fiscal",
            fk_name,
            (column_name,),
            referred_table,
            ("id",),
            "SET NULL",
        )
    if bind.dialect.name == "sqlite":
        if bind.execute(sa.text("PRAGMA quick_check")).fetchone() != ("ok",):
            raise RuntimeError("PF-19B falló PRAGMA quick_check post-downgrade.")
        if bind.execute(sa.text("PRAGMA foreign_key_check")).fetchone() is not None:
            raise RuntimeError("PF-19B falló foreign_key_check post-downgrade.")


def downgrade() -> None:
    """Retira PF-19B solo si permanece exactamente en su estado inicial."""
    _verificar_backup_sqlite()
    _verificar_downgrade()

    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.drop_constraint("fk_intento_guarda_rece_compuesta", type_="foreignkey")
        batch_op.drop_constraint("fk_intento_guarda_rece_simple", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_intento_grupo_snapshot_rece_exacto", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_intento_grupo_empresa", type_="foreignkey")
        batch_op.drop_constraint("fk_intento_lote_empresa", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_intento_revision_rece_compuesta", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_intento_punto_empresa", type_="foreignkey")
        batch_op.drop_constraint("fk_intento_operacion_empresa", type_="foreignkey")
        batch_op.drop_constraint(
            "ck_intentos_emision_fiscal_snapshot_rece_completo", type_="check"
        )
        batch_op.drop_column("guarda_rece_id")
        batch_op.drop_column("punto_venta_revision_fiscal")
        batch_op.drop_column("punto_venta_elegibilidad_revision_id")
        batch_op.drop_column("ambiente")

    _reemplazar_fk_simple_intento(
        "lote_id",
        "lotes_comprobantes",
        ondelete="SET NULL",
    )
    _reemplazar_fk_simple_intento(
        "grupo_id",
        "lotes_comprobantes_grupos",
        ondelete="SET NULL",
    )

    op.drop_index(
        "uq_guarda_rece_activa", table_name="puntos_venta_guardas_emision_rece"
    )
    op.drop_index(
        "ix_guarda_rece_operacion", table_name="puntos_venta_guardas_emision_rece"
    )
    op.drop_index(
        op.f("ix_puntos_venta_guardas_emision_rece_id"),
        table_name="puntos_venta_guardas_emision_rece",
    )
    op.drop_table("puntos_venta_guardas_emision_rece")
    op.drop_index(
        op.f("ix_operaciones_idempotentes_elegibilidad_rece_id"),
        table_name="operaciones_idempotentes_elegibilidad_rece",
    )
    op.drop_table("operaciones_idempotentes_elegibilidad_rece")

    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        batch_op.drop_constraint(
            "fk_lotes_grupos_revision_rece_compuesta", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_lotes_grupos_punto_empresa", type_="foreignkey")
        batch_op.drop_constraint("fk_lotes_grupos_lote_empresa", type_="foreignkey")
        batch_op.drop_constraint(
            "uq_lotes_grupos_identidad_fiscal_compuesta", type_="unique"
        )
        batch_op.drop_constraint(
            "ck_lotes_grupos_snapshot_rece_completo", type_="check"
        )
        batch_op.drop_column("punto_venta_revision_fiscal")
        batch_op.drop_column("punto_venta_elegibilidad_revision_id")
        batch_op.drop_column("ambiente")
        batch_op.drop_column("punto_venta_id")

    op.drop_index(
        "uq_lotes_comprobantes_grupos_id_empresa",
        table_name="lotes_comprobantes_grupos",
    )
    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        batch_op.drop_column("empresa_id")

    op.drop_index(
        op.f("ix_puntos_venta_elegibilidad_rece_actual_id"),
        table_name="puntos_venta_elegibilidad_rece_actual",
    )
    op.drop_table("puntos_venta_elegibilidad_rece_actual")
    op.drop_index(
        op.f("ix_puntos_venta_elegibilidad_rece_revisiones_id"),
        table_name="puntos_venta_elegibilidad_rece_revisiones",
    )
    op.drop_table("puntos_venta_elegibilidad_rece_revisiones")

    op.drop_index("uq_lotes_comprobantes_id_empresa", table_name="lotes_comprobantes")
    op.drop_index(
        "uq_operaciones_idempotentes_id_empresa",
        table_name="operaciones_idempotentes",
    )
    with op.batch_alter_table("operaciones_idempotentes") as batch_op:
        batch_op.drop_constraint(
            "ck_operaciones_idempotentes_rece_snapshot_hash", type_="check"
        )
        batch_op.drop_column("rece_snapshot_hash")
    op.drop_index("uq_puntos_venta_id_empresa", table_name="puntos_venta")
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.drop_constraint(
            "ck_puntos_venta_revision_fiscal_positiva", type_="check"
        )
        batch_op.drop_column("revision_fiscal")
    _verificar_downgrade_aplicado()
