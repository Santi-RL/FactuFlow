"""Descargas contra PostgreSQL explícitamente desechable, con permisos reales."""

from io import BytesIO
from datetime import date
import asyncio
from zipfile import ZipFile
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.empresa import Empresa
from app.models.comprobante import Comprobante
from app.models.usuario import Usuario
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from tests.postgresql_harness import require_disposable_postgres_url
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.test_descargas_pdf import documentos


@pytest.mark.parametrize("admin", [False, True])
async def test_postgres_seleccion_fija_y_zip_aislado(
    monkeypatch, synthetic_user_password_hash, admin
):
    url = require_disposable_postgres_url(purpose="descargas PDF/ZIP PF-18/PF-17")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url, pool_size=1, max_overflow=0)
    sesiones = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sesiones() as db:
            ficha = dict(
                condicion_iva="RI",
                domicilio="Calle sintética",
                localidad="Localidad sintética",
                provincia="Provincia sintética",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            empresa = Empresa(
                razon_social="Emisor sintético", cuit="20123456789", **ficha
            )
            otro = Empresa(
                razon_social="Otro emisor sintético", cuit="20999999999", **ficha
            )
            usuario = Usuario(
                email="pdf@example.test",
                nombre="Operador sintético",
                activo=True,
                es_admin=admin,
                hashed_password=synthetic_user_password_hash,
            )
            db.add_all([empresa, otro, usuario])
            await db.flush()
            db.add(
                UsuarioEmisorAcceso(
                    usuario_id=usuario.id,
                    empresa_id=empresa.id,
                    origen="migracion_legacy",
                )
            )
            await db.commit()
            empresa_id = empresa.id
            ids = await documentos(db, empresa_id)
            ajenos = await documentos(db, otro.id, 1)

            async def get_test_db():
                async with sesiones() as request_db:
                    yield request_db

            app.dependency_overrides[get_db] = get_test_db
            token = create_access_token({"sub": "pdf@example.test"})
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Empresa-Id": str(empresa_id),
            }

            empezo = asyncio.Event()
            continuar = asyncio.Event()

            async def render(c, *args):
                assert not db.in_transaction()
                if not empezo.is_set():
                    assert engine.pool.checkedout() == 0
                    empezo.set()
                    await continuar.wait()
                return f"%PDF-{c.id}".encode()

            renderer = AsyncMock(side_effect=render)
            monkeypatch.setattr(
                "app.api.pdf.pdf_service.generar_pdf_comprobante", renderer
            )
            async with AsyncClient(
                transport=ASGITransport(app), base_url="http://test"
            ) as client:
                seleccion = await client.get("/api/pdf/seleccion", headers=headers)
                assert seleccion.json() == {"ids": ids, "total": 25}
                original = await db.get(Comprobante, ids[0])
                valores = {
                    col.name: getattr(original, col.name)
                    for col in Comprobante.__table__.columns
                    if col.name not in {"id", "numero"}
                }
                db.add(Comprobante(**valores, numero=26))
                await db.commit()
                tarea = asyncio.create_task(
                    client.post("/api/pdf/zip", json={"ids": ids}, headers=headers)
                )
                try:
                    await asyncio.wait_for(empezo.wait(), 5)
                    # The sole connection remains available during a suspended render.
                    lectura = await asyncio.wait_for(
                        client.get("/api/pdf/seleccion", headers=headers), 5
                    )
                    assert lectura.json()["total"] == 26
                finally:
                    continuar.set()
                response = await tarea
                assert response.status_code == 200
                with ZipFile(BytesIO(response.content)) as z:
                    assert {z.read(n) for n in z.namelist()} == {
                        f"%PDF-{i}".encode() for i in ids
                    }
                renderer.reset_mock()
                response = await client.post(
                    "/api/pdf/zip", json={"ids": ids + ajenos}, headers=headers
                )
                assert response.status_code == 404
                assert "fallidos" not in response.text
                renderer.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
        await _reset_schema(url)
