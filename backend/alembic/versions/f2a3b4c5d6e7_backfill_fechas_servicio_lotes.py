"""backfill_fechas_servicio_lotes

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-14 00:00:00.000000

"""

from __future__ import annotations

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reconstruye fechas de servicio desde payloads historicos de lotes."""
    connection = op.get_bind()
    grupos = connection.execute(
        sa.text(
            """
            SELECT
                g.comprobante_id,
                g.payload_json,
                c.fecha_servicio_desde,
                c.fecha_servicio_hasta,
                c.fecha_vto_pago,
                c.fecha_vencimiento
            FROM lotes_comprobantes_grupos AS g
            JOIN comprobantes AS c ON c.id = g.comprobante_id
            WHERE g.comprobante_id IS NOT NULL
              AND g.payload_json IS NOT NULL
              AND (
                c.fecha_servicio_desde IS NULL
                OR c.fecha_servicio_hasta IS NULL
                OR c.fecha_vto_pago IS NULL
                OR c.fecha_vencimiento IS NULL
              )
            """
        )
    )

    for grupo in grupos.mappings():
        payload = _parse_payload(grupo["payload_json"])
        values: dict[str, Any] = {"id": grupo["comprobante_id"]}
        assignments: list[str] = []

        for column in (
            "fecha_servicio_desde",
            "fecha_servicio_hasta",
            "fecha_vto_pago",
        ):
            fecha_payload = payload.get(column)
            if fecha_payload and grupo[column] is None:
                values[column] = fecha_payload
                assignments.append(f"{column} = :{column}")

        if payload.get("fecha_vto_pago") and grupo["fecha_vencimiento"] is None:
            values["fecha_vencimiento"] = payload["fecha_vto_pago"]
            assignments.append("fecha_vencimiento = :fecha_vencimiento")

        if assignments:
            connection.execute(
                sa.text(
                    f"""
                    UPDATE comprobantes
                    SET {", ".join(assignments)}
                    WHERE id = :id
                    """
                ),
                values,
            )


def downgrade() -> None:
    """No revierte el backfill porque restaura datos historicos reales."""


def _parse_payload(payload_json: Any) -> dict[str, Any]:
    """Normaliza JSON de SQLAlchemy/SQLite/PostgreSQL a dict."""
    if isinstance(payload_json, dict):
        return payload_json
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
