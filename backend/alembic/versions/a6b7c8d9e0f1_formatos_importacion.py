"""formatos_importacion

Revision ID: a6b7c8d9e0f1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-08 00:00:00.000000

"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FORMATO_BANCARIO_CONFIG = {
    "tipo": "extracto_bancario_creditos",
    "header_row": 1,
    "modo_agrupacion": "fila",
    "campos": {
        "fecha_origen": {
            "origen": "header",
            "encabezados": ["Fecha"],
            "transformacion": "fecha",
            "requerido": False,
        },
        "importe_total": {
            "origen": "header",
            "encabezados": [
                "Creditos",
                "Créditos",
                "Credito",
                "Crédito",
                "Importe Credito",
                "Importe Crédito",
                "Importe acreditado",
            ],
            "transformacion": "decimal",
            "requerido": True,
        },
        "cliente_razon_social": {
            "origen": "header",
            "encabezados": [
                "Leyendas Adicionales1",
                "Leyendas Adicionales 1",
                "Nombre",
                "Cliente",
                "Razon Social",
                "Razón Social",
            ],
            "transformacion": "texto",
            "requerido": False,
            "default": "",
        },
        "cliente_numero_documento": {
            "origen": "header",
            "encabezados": [
                "Leyendas Adicionales2",
                "Leyendas Adicionales 2",
                "CUIT",
                "Documento",
                "Numero Documento",
                "Número Documento",
            ],
            "transformacion": "documento",
            "requerido": False,
            "default": "",
        },
        "punto_venta_numero": {
            "origen": "header",
            "encabezados": [
                "Pto Vta",
                "Pto. Vta.",
                "Punto Venta",
                "Punto de Venta",
                "PV",
            ],
            "transformacion": "entero",
            "requerido": True,
        },
        "tipo_comprobante": {"origen": "constante", "valor": 11},
        "concepto": {"origen": "constante", "valor": 1},
        "cliente_condicion_iva": {
            "origen": "constante",
            "valor": "Consumidor Final",
        },
        "item_descripcion": {
            "origen": "constante",
            "valor": "Cobro registrado en cuenta bancaria",
        },
        "item_cantidad": {"origen": "constante", "valor": 1},
        "item_unidad": {"origen": "constante", "valor": "unidad"},
        "item_iva_porcentaje": {"origen": "constante", "valor": 0},
        "item_descuento_porcentaje": {"origen": "constante", "valor": 0},
        "guardar_cliente": {"origen": "constante", "valor": False},
    },
}


def upgrade() -> None:
    op.create_table(
        "formatos_importacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("alcance", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_formatos_importacion_id"),
        "formatos_importacion",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_formatos_importacion_empresa",
        "formatos_importacion",
        ["empresa_id", "activo"],
        unique=False,
    )
    op.create_index(
        "ix_formatos_importacion_alcance",
        "formatos_importacion",
        ["alcance", "activo"],
        unique=False,
    )

    op.create_table(
        "formatos_importacion_versiones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("configuracion_json", sa.JSON(), nullable=False),
        sa.Column("headers_firma_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("formato_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["formato_id"], ["formatos_importacion.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "formato_id",
            "version",
            name="uq_formatos_importacion_versiones_formato_version",
        ),
    )
    op.create_index(
        op.f("ix_formatos_importacion_versiones_id"),
        "formatos_importacion_versiones",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_formatos_importacion_versiones_formato_estado",
        "formatos_importacion_versiones",
        ["formato_id", "estado"],
        unique=False,
    )

    op.create_table(
        "formatos_importacion_campos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campo_destino", sa.String(length=100), nullable=False),
        sa.Column("origen_tipo", sa.String(length=20), nullable=False),
        sa.Column("encabezado", sa.String(length=255), nullable=True),
        sa.Column("alias_json", sa.JSON(), nullable=True),
        sa.Column("letra_columna", sa.String(length=10), nullable=True),
        sa.Column("indice_columna", sa.Integer(), nullable=True),
        sa.Column("valor_constante_json", sa.JSON(), nullable=True),
        sa.Column("requerido", sa.Boolean(), nullable=False),
        sa.Column("transformacion", sa.String(length=50), nullable=True),
        sa.Column("valor_default_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["formatos_importacion_versiones.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id",
            "campo_destino",
            name="uq_formatos_importacion_campos_version_campo",
        ),
    )
    op.create_index(
        op.f("ix_formatos_importacion_campos_id"),
        "formatos_importacion_campos",
        ["id"],
        unique=False,
    )

    op.create_table(
        "formatos_importacion_reglas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("configuracion_json", sa.JSON(), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["formatos_importacion_versiones.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_formatos_importacion_reglas_id"),
        "formatos_importacion_reglas",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_formatos_importacion_reglas_version",
        "formatos_importacion_reglas",
        ["version_id", "activo"],
        unique=False,
    )

    with op.batch_alter_table("lotes_comprobantes") as batch_op:
        batch_op.add_column(sa.Column("mapeo_usado_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("headers_detectados_json", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("formato_importacion_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("formato_importacion_version_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_lotes_comprobantes_formato_importacion",
            "formatos_importacion",
            ["formato_importacion_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_lotes_comprobantes_formato_importacion_version",
            "formatos_importacion_versiones",
            ["formato_importacion_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    metadata = sa.MetaData()
    formatos = sa.Table(
        "formatos_importacion",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nombre", sa.String),
        sa.Column("descripcion", sa.Text),
        sa.Column("alcance", sa.String),
        sa.Column("activo", sa.Boolean),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("empresa_id", sa.Integer),
    )
    versiones = sa.Table(
        "formatos_importacion_versiones",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.Integer),
        sa.Column("estado", sa.String),
        sa.Column("configuracion_json", sa.JSON),
        sa.Column("headers_firma_json", sa.JSON),
        sa.Column("created_at", sa.DateTime),
        sa.Column("formato_id", sa.Integer),
    )
    campos = sa.Table(
        "formatos_importacion_campos",
        metadata,
        sa.Column("campo_destino", sa.String),
        sa.Column("origen_tipo", sa.String),
        sa.Column("encabezado", sa.String),
        sa.Column("alias_json", sa.JSON),
        sa.Column("valor_constante_json", sa.JSON),
        sa.Column("requerido", sa.Boolean),
        sa.Column("transformacion", sa.String),
        sa.Column("valor_default_json", sa.JSON),
        sa.Column("created_at", sa.DateTime),
        sa.Column("version_id", sa.Integer),
    )
    reglas = sa.Table(
        "formatos_importacion_reglas",
        metadata,
        sa.Column("nombre", sa.String),
        sa.Column("tipo", sa.String),
        sa.Column("configuracion_json", sa.JSON),
        sa.Column("orden", sa.Integer),
        sa.Column("activo", sa.Boolean),
        sa.Column("created_at", sa.DateTime),
        sa.Column("version_id", sa.Integer),
    )

    now = datetime.utcnow()
    bind = op.get_bind()
    formato_result = bind.execute(
        sa.insert(formatos).values(
            nombre="Extracto bancario - creditos IVA exento",
            descripcion=(
                "Formato global para extractos donde Creditos es el importe, "
                "Leyendas Adicionales1 el receptor, Leyendas Adicionales2 el "
                "documento y Pto Vta el punto de venta."
            ),
            alcance="global",
            activo=True,
            created_at=now,
            updated_at=now,
            empresa_id=None,
        )
    )
    formato_id = formato_result.inserted_primary_key[0]
    version_result = bind.execute(
        sa.insert(versiones).values(
            version=1,
            estado="vigente",
            configuracion_json=FORMATO_BANCARIO_CONFIG,
            headers_firma_json={
                "requeridos": ["Creditos", "Pto Vta"],
                "opcionales": [
                    "Fecha",
                    "Leyendas Adicionales1",
                    "Leyendas Adicionales2",
                ],
            },
            created_at=now,
            formato_id=formato_id,
        )
    )
    version_id = version_result.inserted_primary_key[0]

    campo_rows = []
    for campo_destino, config in FORMATO_BANCARIO_CONFIG["campos"].items():
        campo_rows.append(
            {
                "campo_destino": campo_destino,
                "origen_tipo": config.get("origen", "header"),
                "encabezado": (config.get("encabezados") or [None])[0],
                "alias_json": config.get("encabezados"),
                "valor_constante_json": config.get("valor"),
                "requerido": bool(config.get("requerido", False)),
                "transformacion": config.get("transformacion"),
                "valor_default_json": config.get("default"),
                "created_at": now,
                "version_id": version_id,
            }
        )
    bind.execute(sa.insert(campos), campo_rows)

    bind.execute(
        sa.insert(reglas).values(
            nombre="Cada fila genera un comprobante",
            tipo="agrupacion",
            configuracion_json={"modo": "fila"},
            orden=1,
            activo=True,
            created_at=now,
            version_id=version_id,
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("lotes_comprobantes") as batch_op:
        batch_op.drop_constraint(
            "fk_lotes_comprobantes_formato_importacion_version",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_lotes_comprobantes_formato_importacion",
            type_="foreignkey",
        )
        batch_op.drop_column("formato_importacion_version_id")
        batch_op.drop_column("formato_importacion_id")
        batch_op.drop_column("headers_detectados_json")
        batch_op.drop_column("mapeo_usado_json")

    op.drop_index(
        "ix_formatos_importacion_reglas_version",
        table_name="formatos_importacion_reglas",
    )
    op.drop_index(
        op.f("ix_formatos_importacion_reglas_id"),
        table_name="formatos_importacion_reglas",
    )
    op.drop_table("formatos_importacion_reglas")
    op.drop_index(
        op.f("ix_formatos_importacion_campos_id"),
        table_name="formatos_importacion_campos",
    )
    op.drop_table("formatos_importacion_campos")
    op.drop_index(
        "ix_formatos_importacion_versiones_formato_estado",
        table_name="formatos_importacion_versiones",
    )
    op.drop_index(
        op.f("ix_formatos_importacion_versiones_id"),
        table_name="formatos_importacion_versiones",
    )
    op.drop_table("formatos_importacion_versiones")
    op.drop_index(
        "ix_formatos_importacion_alcance",
        table_name="formatos_importacion",
    )
    op.drop_index(
        "ix_formatos_importacion_empresa",
        table_name="formatos_importacion",
    )
    op.drop_index(op.f("ix_formatos_importacion_id"), table_name="formatos_importacion")
    op.drop_table("formatos_importacion")
