"""integridad_fiscal_estados

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ESTADOS_INTENTO_FISCAL_SQL = (
    "'autorizado', 'en_proceso', 'fallido_verificado', "
    "'rechazado_arca', 'requiere_reconciliacion'"
)
ESTADOS_RESERVA_ACTIVA_SQL = "'autorizado', 'en_proceso', 'requiere_reconciliacion'"
ESTADOS_COMPROBANTE_SQL = "'autorizado', 'borrador', 'pendiente', 'rechazado'"
CHECKS_ESPERADOS = {
    "intentos_emision_fiscal": {"ck_intentos_emision_fiscal_estado_valido"},
    "comprobantes": {
        "ck_comprobantes_estado_valido",
        "ck_comprobantes_estado_cae_coherente",
    },
}


def _contar(query: str) -> int:
    """Ejecuta una consulta agregada de preflight sin exponer filas fiscales."""
    value = op.get_bind().execute(sa.text(query)).scalar_one()
    return int(value)


def _verificar_datos_legacy() -> None:
    """Aborta antes del DDL cuando existen datos fiscales ambiguos."""
    conflictos = {
        "intentos_estado_desconocido": _contar(
            "SELECT COUNT(*) FROM intentos_emision_fiscal "
            f"WHERE estado NOT IN ({ESTADOS_INTENTO_FISCAL_SQL})"
        ),
        "comprobantes_estado_desconocido": _contar(
            "SELECT COUNT(*) FROM comprobantes "
            f"WHERE estado NOT IN ({ESTADOS_COMPROBANTE_SQL})"
        ),
        "comprobantes_autorizados_incompletos": _contar(
            "SELECT COUNT(*) FROM comprobantes "
            "WHERE estado = 'autorizado' "
            "AND (cae IS NULL OR trim(cae) = '' OR length(trim(cae)) <> 14 "
            "OR cae_vencimiento IS NULL)"
        ),
        "comprobantes_no_autorizados_con_cae": _contar(
            "SELECT COUNT(*) FROM comprobantes "
            "WHERE estado <> 'autorizado' "
            "AND (cae IS NOT NULL OR cae_vencimiento IS NOT NULL)"
        ),
        "reservas_activas_duplicadas": _contar(
            "SELECT COUNT(*) FROM ("
            "SELECT empresa_id, punto_venta_id, tipo_comprobante, "
            "numero_planificado FROM intentos_emision_fiscal "
            "WHERE numero_planificado IS NOT NULL "
            f"AND estado IN ({ESTADOS_RESERVA_ACTIVA_SQL}) "
            "GROUP BY empresa_id, punto_venta_id, tipo_comprobante, "
            "numero_planificado HAVING COUNT(*) > 1"
            ") AS reservas_duplicadas"
        ),
    }
    activos = [
        f"{categoria}={cantidad}"
        for categoria, cantidad in conflictos.items()
        if cantidad > 0
    ]
    if activos:
        raise RuntimeError(
            "PF-01B abortó antes de modificar el esquema porque existen "
            "datos fiscales ambiguos. Revisá y reconciliá cada categoría: "
            + ", ".join(activos)
            + "."
        )


def _crear_constraints() -> None:
    """Crea restricciones portables de dominio y coherencia fiscal."""
    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.create_check_constraint(
            "ck_intentos_emision_fiscal_estado_valido",
            f"estado IN ({ESTADOS_INTENTO_FISCAL_SQL})",
        )

    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.create_check_constraint(
            "ck_comprobantes_estado_valido",
            f"estado IN ({ESTADOS_COMPROBANTE_SQL})",
        )
        batch_op.create_check_constraint(
            "ck_comprobantes_estado_cae_coherente",
            "((estado = 'autorizado' "
            "AND cae IS NOT NULL "
            "AND length(trim(cae)) = 14 "
            "AND cae_vencimiento IS NOT NULL) "
            "OR (estado <> 'autorizado' "
            "AND cae IS NULL "
            "AND cae_vencimiento IS NULL))",
        )


def _verificar_constraints() -> None:
    """Confirma que el esquema contiene todas las restricciones esperadas."""
    inspector = sa.inspect(op.get_bind())
    faltantes: list[str] = []
    for table_name, esperados in CHECKS_ESPERADOS.items():
        existentes = {
            constraint.get("name")
            for constraint in inspector.get_check_constraints(table_name)
        }
        faltantes.extend(
            f"{table_name}.{constraint_name}"
            for constraint_name in sorted(esperados - existentes)
        )
    if faltantes:
        raise RuntimeError(
            "PF-01B no pudo verificar los constraints creados: "
            + ", ".join(faltantes)
            + "."
        )


def upgrade() -> None:
    """Agrega integridad persistente sin normalizar datos fiscales ambiguos."""
    _verificar_datos_legacy()
    _crear_constraints()
    _verificar_constraints()


def downgrade() -> None:
    """Retira solo los checks de PF-01B sin reescribir datos fiscales."""
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.drop_constraint(
            "ck_comprobantes_estado_cae_coherente",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_comprobantes_estado_valido",
            type_="check",
        )

    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.drop_constraint(
            "ck_intentos_emision_fiscal_estado_valido",
            type_="check",
        )
