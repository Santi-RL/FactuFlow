"""Contratos de zona y compatibilidad de instantes operativos en HTTP."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lote_comprobante import LoteComprobante
from app.schemas.utc_datetime import UTCResponseDateTime


@pytest.mark.parametrize(
    "source",
    [
        datetime(2026, 10, 3, 1, 30, 0, 123456),
        datetime(2026, 10, 3, 1, 30, 0, 123456, tzinfo=timezone.utc),
        datetime(
            2026,
            10,
            2,
            22,
            30,
            0,
            123456,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
        datetime(
            2026,
            10,
            3,
            10,
            30,
            0,
            123456,
            tzinfo=timezone(timedelta(hours=9)),
        ),
    ],
)
def test_response_datetime_conserva_instante_y_objeto_python(source):
    """Offsets equivalentes y el UTC persistido producen un único instante."""
    adapter = TypeAdapter(UTCResponseDateTime)
    assert adapter.dump_python(source) is source
    output = adapter.dump_python(source, mode="json")
    assert output == "2026-10-03T01:30:00.123456Z"
    parsed = datetime.fromisoformat(output.replace("Z", "+00:00"))
    assert parsed == datetime(2026, 10, 3, 1, 30, 0, 123456, tzinfo=timezone.utc)
    assert adapter.json_schema(mode="serialization")["format"] == "date-time"


@pytest.mark.asyncio
async def test_listado_lote_zona_explicita_sin_reescribir_base(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """Consultar el lote comunica UTC; guarda los relojes y metadata originales."""
    instant = datetime(2026, 10, 3, 1, 30)
    metadata = {"fecha_historica_sin_zona": "2026-10-03T01:30:00"}
    lote = LoteComprobante(
        empresa_id=test_empresa.id,
        nombre_archivo="lote-sintetico-tiempo.xlsx",
        archivo_hash="a" * 64,
        estado="validado",
        modo_procesamiento="sync",
        procesamiento_async=False,
        created_at=instant,
        updated_at=instant,
        started_at=None,
        finished_at=None,
        metadata_json=metadata,
    )
    db_session.add(lote)
    await db_session.commit()
    await db_session.refresh(lote)
    response = await client.get("/api/lotes-comprobantes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()[0]
    assert data["created_at"] == "2026-10-03T01:30:00Z"
    assert data["started_at"] is None
    assert data["metadata_json"] == metadata
    await db_session.refresh(lote)
    assert lote.created_at == instant
    assert lote.created_at.tzinfo is None
    assert lote.metadata_json == metadata
