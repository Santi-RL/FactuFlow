"""duplicados_lotes_v2

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-09-05
"""

from decimal import Decimal, InvalidOperation
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_grupos() -> None:
    """Acredita sólo payloads legacy que validan bajo el contrato estricto."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT g.id, g.payload_json, g.total_estimado, "
            "g.empresa_id, g.punto_venta_id, g.punto_venta_numero, g.ambiente, "
            "l.empresa_id AS lote_empresa_id, "
            "p.id AS punto_encontrado, p.empresa_id AS punto_empresa_id, "
            "p.numero AS punto_numero "
            "FROM lotes_comprobantes_grupos g "
            "LEFT JOIN lotes_comprobantes l ON l.id = g.lote_id "
            "LEFT JOIN puntos_venta p ON p.id = g.punto_venta_id"
        )
    ).mappings()
    from app.schemas.comprobante import EmitirComprobanteRequest
    from app.services.duplicados_lotes_service import (
        decimal_canonico,
        huella_fiscal_completa_v2,
        identidad_entrada_v2,
    )

    for row in rows:
        payload = row["payload_json"]
        punto = row["punto_venta_numero"]
        cobertura = "no_comprobable"
        huella = None
        fecha = None
        moneda = None
        cotizacion = None
        total_centavos = None
        nombre_hash = None
        documento_hash = None
        nombre_original = None
        tipo_documento_original = None
        numero_documento_original = None
        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
            request = EmitirComprobanteRequest.model_validate(payload or {})
            total = Decimal(str(row["total_estimado"]))
            identidad_coherente = bool(
                row["empresa_id"] is not None
                and row["lote_empresa_id"] is not None
                and int(row["empresa_id"]) == int(row["lote_empresa_id"])
                and int(request.empresa_id) == int(row["empresa_id"])
                and row["ambiente"] in {"homologacion", "produccion"}
                and row["punto_venta_id"] is not None
                and row["punto_encontrado"] is not None
                and int(request.punto_venta_id) == int(row["punto_venta_id"])
                and int(row["punto_empresa_id"]) == int(row["empresa_id"])
                and punto is not None
                and 1 <= int(punto) <= 99999
                and int(row["punto_numero"]) == int(punto)
                and total.is_finite()
            )
            if not identidad_coherente:
                raise ValueError("El grupo legacy no acredita su contexto fiscal.")
            identidad = identidad_entrada_v2(
                tipo_documento=payload.get("tipo_documento"),
                numero_documento=payload.get("numero_documento"),
                razon_social=payload.get("razon_social"),
            )
            huella = huella_fiscal_completa_v2(
                request,
                punto_venta_numero=int(punto),
            )
            nombre_hash = identidad["nombre_hash"]
            documento_hash = identidad["documento_hash"]
            nombre_original = identidad["nombre_original"]
            tipo_documento_original = identidad["tipo_documento_original"]
            numero_documento_original = identidad["numero_documento_original"]
            fecha = request.fecha_emision
            moneda = request.moneda
            cotizacion = decimal_canonico(request.cotizacion)
            total_centavos = int(
                (total.quantize(Decimal("0.01")) * 100).to_integral_exact()
            )
            cobertura = "parcial_legacy"
        except (InvalidOperation, TypeError, ValueError, json.JSONDecodeError):
            cobertura = "no_comprobable"
            huella = None
            fecha = None
            moneda = None
            cotizacion = None
            total_centavos = None
            nombre_hash = None
            documento_hash = None
            nombre_original = None
            tipo_documento_original = None
            numero_documento_original = None
        bind.execute(
            sa.text(
                "UPDATE lotes_comprobantes_grupos "
                "SET duplicados_version=:version, "
                "duplicados_cobertura=:cobertura, "
                "huella_fiscal_completa=:huella, "
                "identidad_nombre_hash=:nombre_hash, "
                "identidad_documento_hash=:documento_hash, "
                "identidad_nombre_original=:nombre_original, "
                "identidad_tipo_documento_original=:tipo_documento_original, "
                "identidad_numero_documento_original=:numero_documento_original, "
                "fecha_emision_normalizada=:fecha, "
                "moneda_duplicados=:moneda, "
                "cotizacion_duplicados=:cotizacion, "
                "total_centavos=:total_centavos "
                "WHERE id=:id"
            ),
            {
                "version": "duplicados_lotes/v2",
                "cobertura": cobertura,
                "huella": huella,
                "nombre_hash": nombre_hash,
                "documento_hash": documento_hash,
                "nombre_original": nombre_original,
                "tipo_documento_original": tipo_documento_original,
                "numero_documento_original": numero_documento_original,
                "fecha": fecha,
                "moneda": moneda,
                "cotizacion": cotizacion,
                "total_centavos": total_centavos,
                "id": row["id"],
            },
        )


def upgrade() -> None:
    op.create_table(
        "lotes_duplicados_coordinacion",
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "ambiente IN ('homologacion', 'produccion')",
            name="ck_lotes_duplicados_coordinacion_ambiente",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("empresa_id", "ambiente"),
    )
    op.execute(
        sa.text(
            "INSERT INTO lotes_duplicados_coordinacion "
            "(empresa_id, ambiente, revision, updated_at) "
            "SELECT id, 'homologacion', 0, CURRENT_TIMESTAMP FROM empresas"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO lotes_duplicados_coordinacion "
            "(empresa_id, ambiente, revision, updated_at) "
            "SELECT id, 'produccion', 0, CURRENT_TIMESTAMP FROM empresas"
        )
    )

    with op.batch_alter_table("operaciones_idempotentes") as batch_op:
        batch_op.add_column(
            sa.Column("control_duplicados_json", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("duplicados_version", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(sa.Column("operacion_raiz_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "solicitante_nombre_snapshot", sa.String(length=255), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("solicitud_emision_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_operaciones_idempotentes_operacion_raiz",
            "operaciones_idempotentes",
            ["operacion_raiz_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.add_column(
            sa.Column(
                "solicitante_nombre_snapshot", sa.String(length=255), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("solicitud_arca_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("resultado_fiscal_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "lotes_duplicados_evidencias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operacion_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("generacion", sa.Integer(), nullable=False),
        sa.Column("formato", sa.String(length=40), nullable=False),
        sa.Column("evidencia_id", sa.String(length=100), nullable=True),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("control_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("aceptacion_id", sa.String(length=100), nullable=True),
        sa.Column("aceptada_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("aceptada_por_nombre", sa.String(length=255), nullable=True),
        sa.Column("aceptada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aceptacion_origen_generacion_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "formato = 'duplicados_relacion/1'",
            name="ck_lotes_duplicados_evidencias_formato",
        ),
        sa.CheckConstraint(
            "length(snapshot_hash) = 64",
            name="ck_lotes_duplicados_evidencias_snapshot_hash",
        ),
        sa.CheckConstraint(
            "generacion > 0", name="ck_lotes_duplicados_evidencias_generacion"
        ),
        sa.CheckConstraint(
            "((aceptada_por_usuario_id IS NULL AND aceptada_por_nombre IS NULL "
            "AND aceptada_at IS NULL AND aceptacion_origen_generacion_id IS NULL) "
            "OR (aceptacion_id IS NOT NULL AND aceptada_por_usuario_id IS NOT NULL "
            "AND aceptada_por_nombre IS NOT NULL AND aceptada_at IS NOT NULL))",
            name="ck_lotes_duplicados_evidencias_aceptacion",
        ),
        sa.ForeignKeyConstraint(
            ["operacion_id"], ["operaciones_idempotentes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["lote_id"], ["lotes_comprobantes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["aceptada_por_usuario_id"], ["usuarios.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["aceptacion_origen_generacion_id"],
            ["lotes_duplicados_evidencias.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operacion_id",
            "generacion",
            name="uq_lotes_duplicados_evidencias_operacion_generacion",
        ),
        sa.UniqueConstraint(
            "id",
            "operacion_id",
            "empresa_id",
            "lote_id",
            "ambiente",
            name="uq_lotes_duplicados_evidencias_scope",
        ),
    )
    op.create_index(
        "ix_lotes_duplicados_evidencias_consulta",
        "lotes_duplicados_evidencias",
        ["empresa_id", "ambiente", "lote_id", "evidencia_id"],
    )
    op.create_table(
        "lotes_duplicados_coincidencias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generacion_id", sa.Integer(), nullable=False),
        sa.Column("operacion_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("bloque_clave", sa.String(length=64), nullable=False),
        sa.Column("clase", sa.String(length=30), nullable=False),
        sa.Column("antecedente_clave", sa.String(length=100), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "clase IN ('interna_nombre', 'interna_documento', 'completa', "
            "'parcial_nombre', 'parcial_documento', 'individual_legacy')",
            name="ck_lotes_duplicados_coincidencias_clase",
        ),
        sa.ForeignKeyConstraint(
            ["generacion_id", "operacion_id", "empresa_id", "lote_id", "ambiente"],
            [
                "lotes_duplicados_evidencias.id",
                "lotes_duplicados_evidencias.operacion_id",
                "lotes_duplicados_evidencias.empresa_id",
                "lotes_duplicados_evidencias.lote_id",
                "lotes_duplicados_evidencias.ambiente",
            ],
            name="fk_lotes_duplicados_coincidencias_generacion_scope",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generacion_id",
            "bloque_clave",
            name="uq_lotes_duplicados_coincidencias_bloque",
        ),
    )
    op.create_index(
        "ix_lotes_duplicados_coincidencias_generacion_clase",
        "lotes_duplicados_coincidencias",
        ["generacion_id", "clase", "bloque_clave"],
    )
    op.create_table(
        "lotes_duplicados_coincidencias_miembros",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bloque_id", sa.Integer(), nullable=False),
        sa.Column("lado", sa.String(length=10), nullable=False),
        sa.Column("miembro_clave", sa.String(length=100), nullable=False),
        sa.Column("grupo_id", sa.Integer(), nullable=True),
        sa.Column("comprobante_id", sa.Integer(), nullable=True),
        sa.Column("nombre_hash", sa.String(length=64), nullable=True),
        sa.Column("documento_hash", sa.String(length=64), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column("relevancia", sa.String(length=20), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "lado IN ('actual', 'anterior')",
            name="ck_lotes_duplicados_miembros_lado",
        ),
        sa.CheckConstraint(
            "ordinal IS NULL OR ordinal >= 0",
            name="ck_lotes_duplicados_miembros_ordinal",
        ),
        sa.CheckConstraint(
            "relevancia IN ('actual', 'autorizado', 'reservado', 'incierto')",
            name="ck_lotes_duplicados_miembros_relevancia",
        ),
        sa.CheckConstraint(
            "((grupo_id IS NOT NULL AND comprobante_id IS NULL) OR "
            "(grupo_id IS NULL AND comprobante_id IS NOT NULL))",
            name="ck_lotes_duplicados_miembros_entidad",
        ),
        sa.ForeignKeyConstraint(
            ["bloque_id"], ["lotes_duplicados_coincidencias.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bloque_id",
            "lado",
            "miembro_clave",
            name="uq_lotes_duplicados_miembros_clave",
        ),
        sa.UniqueConstraint(
            "bloque_id",
            "lado",
            "ordinal",
            name="uq_lotes_duplicados_miembros_ordinal",
        ),
    )
    op.create_index(
        "ix_lotes_duplicados_miembros_pagina",
        "lotes_duplicados_coincidencias_miembros",
        ["bloque_id", "lado", "ordinal", "miembro_clave"],
    )
    op.create_index(
        "ix_lotes_duplicados_miembros_nombre",
        "lotes_duplicados_coincidencias_miembros",
        ["bloque_id", "lado", "nombre_hash"],
    )

    with op.batch_alter_table("operaciones_idempotentes") as batch_op:
        batch_op.add_column(
            sa.Column("duplicados_generacion_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_operaciones_idempotentes_duplicados_generacion",
            "lotes_duplicados_evidencias",
            ["duplicados_generacion_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.add_column(
            sa.Column("duplicados_generacion_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_intento_duplicados_generacion_scope",
            "lotes_duplicados_evidencias",
            [
                "duplicados_generacion_id",
                "operacion_id",
                "empresa_id",
                "lote_id",
                "ambiente",
            ],
            ["id", "operacion_id", "empresa_id", "lote_id", "ambiente"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        batch_op.add_column(
            sa.Column("duplicados_version", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("duplicados_cobertura", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("huella_fiscal_completa", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("identidad_nombre_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("identidad_documento_hash", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("identidad_nombre_original", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("identidad_tipo_documento_original", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "identidad_numero_documento_original",
                sa.String(length=20),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("fecha_emision_normalizada", sa.Date(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("moneda_duplicados", sa.String(length=3), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cotizacion_duplicados", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(sa.Column("total_centavos", sa.BigInteger(), nullable=True))
        batch_op.add_column(
            sa.Column("duplicados_reserva_operacion_id", sa.Integer(), nullable=True)
        )

    _backfill_grupos()
    op.create_index(
        "ix_lotes_grupos_dup_huella_lote",
        "lotes_comprobantes_grupos",
        ["empresa_id", "ambiente", "lote_id", "huella_fiscal_completa"],
    )
    partial_columns = [
        "empresa_id",
        "ambiente",
        "tipo_comprobante",
        "punto_venta_numero",
        "fecha_emision_normalizada",
        "moneda_duplicados",
        "cotizacion_duplicados",
        "total_centavos",
    ]
    op.create_index(
        "ix_lotes_grupos_dup_nombre",
        "lotes_comprobantes_grupos",
        [*partial_columns, "identidad_nombre_hash"],
    )
    op.create_index(
        "ix_lotes_grupos_dup_documento",
        "lotes_comprobantes_grupos",
        [*partial_columns, "identidad_documento_hash"],
    )
    op.create_index(
        "ix_lotes_grupos_dup_reserva",
        "lotes_comprobantes_grupos",
        ["duplicados_reserva_operacion_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    evidence = bind.execute(
        sa.text(
            "SELECT (SELECT count(*) FROM operaciones_idempotentes "
            "WHERE control_duplicados_json IS NOT NULL OR duplicados_version IS NOT NULL) + "
            "(SELECT count(*) FROM lotes_comprobantes_grupos "
            "WHERE duplicados_reserva_operacion_id IS NOT NULL OR "
            "duplicados_version IS NOT NULL) + "
            "(SELECT count(*) FROM lotes_duplicados_evidencias)"
        )
    ).scalar_one()
    if evidence:
        raise RuntimeError(
            "El downgrade físico se bloqueó porque existe evidencia de duplicados v2."
        )

    op.drop_index("ix_lotes_grupos_dup_reserva", table_name="lotes_comprobantes_grupos")
    op.drop_index(
        "ix_lotes_grupos_dup_documento", table_name="lotes_comprobantes_grupos"
    )
    op.drop_index("ix_lotes_grupos_dup_nombre", table_name="lotes_comprobantes_grupos")
    op.drop_index(
        "ix_lotes_grupos_dup_huella_lote", table_name="lotes_comprobantes_grupos"
    )
    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        for column in (
            "duplicados_reserva_operacion_id",
            "total_centavos",
            "cotizacion_duplicados",
            "moneda_duplicados",
            "fecha_emision_normalizada",
            "identidad_numero_documento_original",
            "identidad_tipo_documento_original",
            "identidad_nombre_original",
            "identidad_documento_hash",
            "identidad_nombre_hash",
            "huella_fiscal_completa",
            "duplicados_cobertura",
            "duplicados_version",
        ):
            batch_op.drop_column(column)
    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.drop_constraint(
            "fk_intento_duplicados_generacion_scope", type_="foreignkey"
        )
        batch_op.drop_column("duplicados_generacion_id")
        batch_op.drop_column("resultado_fiscal_at")
        batch_op.drop_column("solicitud_arca_at")
        batch_op.drop_column("solicitante_nombre_snapshot")
    with op.batch_alter_table("operaciones_idempotentes") as batch_op:
        batch_op.drop_constraint(
            "fk_operaciones_idempotentes_duplicados_generacion", type_="foreignkey"
        )
        batch_op.drop_column("duplicados_generacion_id")
    op.drop_index(
        "ix_lotes_duplicados_miembros_nombre",
        table_name="lotes_duplicados_coincidencias_miembros",
    )
    op.drop_index(
        "ix_lotes_duplicados_miembros_pagina",
        table_name="lotes_duplicados_coincidencias_miembros",
    )
    op.drop_table("lotes_duplicados_coincidencias_miembros")
    op.drop_index(
        "ix_lotes_duplicados_coincidencias_generacion_clase",
        table_name="lotes_duplicados_coincidencias",
    )
    op.drop_table("lotes_duplicados_coincidencias")
    op.drop_index(
        "ix_lotes_duplicados_evidencias_consulta",
        table_name="lotes_duplicados_evidencias",
    )
    op.drop_table("lotes_duplicados_evidencias")
    with op.batch_alter_table("operaciones_idempotentes") as batch_op:
        batch_op.drop_constraint(
            "fk_operaciones_idempotentes_operacion_raiz", type_="foreignkey"
        )
        batch_op.drop_column("solicitud_emision_at")
        batch_op.drop_column("solicitante_nombre_snapshot")
        batch_op.drop_column("operacion_raiz_id")
        batch_op.drop_column("duplicados_version")
        batch_op.drop_column("control_duplicados_json")
    op.drop_table("lotes_duplicados_coordinacion")
