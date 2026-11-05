"""Selección completa, ZIP atómico, permisos y liberación sin tocar hechos fiscales."""

from datetime import date
from io import BytesIO
import tempfile
from unittest.mock import AsyncMock, patch
from zipfile import ZipFile
import asyncio
from time import perf_counter

import pytest
from sqlalchemy import select, delete
from sqlalchemy import update
from pypdf import PdfReader

from app.models.comprobante import Comprobante
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from tests.test_pdf_api import _crear_comprobante_pdf
from tests.test_lecturas_historicas import crear_historia
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.api.pdf import _ZIPTemporal


async def documentos(db, empresa_id, cantidad=25):
    primero = await _crear_comprobante_pdf(
        db,
        empresa_id,
        estado="autorizado",
        cae="12345678901234",
        cae_vencimiento=date(2026, 2, 13),
    )
    primero.receptor_tipo_documento = 99
    primero.receptor_numero_documento = "0"
    primero.receptor_razon_social = "Cliente sintético"
    primero.receptor_condicion_iva = "Consumidor Final"
    await db.commit()
    ids = [primero.id]
    valores = {
        col.name: getattr(primero, col.name)
        for col in Comprobante.__table__.columns
        if col.name not in {"id", "numero"}
    }
    for numero in range(2, cantidad + 1):
        c = Comprobante(**valores, numero=numero)
        db.add(c)
        await db.flush()
        ids.append(c.id)
    await db.commit()
    return ids


@pytest.mark.asyncio
async def test_seleccion_comparte_filtros_y_supera_una_pagina(
    client, auth_headers, db_session, test_empresa
):
    ids = await documentos(db_session, test_empresa.id)
    params = {"desde": "2026-02-01", "hasta": "2026-02-28", "tipo": 6}
    seleccion = await client.get(
        "/api/pdf/seleccion", params=params, headers=auth_headers
    )
    listado = await client.get(
        "/api/comprobantes/", params=params, headers=auth_headers
    )
    assert seleccion.json() == {"ids": ids, "total": 25}
    assert listado.json()["total"] == 25
    assert len(listado.json()["items"]) == 20
    for filtro in [
        {"hasta": "2026-02-02"},
        {"desde": "2026-02-04"},
        {"tipo": 11},
        {"buscar": "sin-coincidencias"},
    ]:
        r = await client.get("/api/pdf/seleccion", params=filtro, headers=auth_headers)
        assert r.json() == {"ids": [], "total": 0}
    for buscar in ["1", "25"]:
        params["buscar"] = buscar
        s = (
            await client.get("/api/pdf/seleccion", params=params, headers=auth_headers)
        ).json()
        listado_filtrado = (
            await client.get("/api/comprobantes/", params=params, headers=auth_headers)
        ).json()
        assert s["ids"] == sorted(c["id"] for c in listado_filtrado["items"])


@pytest.mark.asyncio
@pytest.mark.parametrize("falla", [None, 0, 9, 18])
async def test_zip_completo_o_ninguno_y_temporal_cerrado(
    client, auth_headers, db_session, test_empresa, falla
):
    ids = await documentos(db_session, test_empresa.id, 19)
    temporales = []
    original = tempfile.TemporaryFile

    def crear(*args, **kwargs):
        archivo = original(*args, **kwargs)
        temporales.append(archivo)
        return archivo

    async def render(c, empresa, lectura):
        assert not db_session.in_transaction()
        if falla is not None and c.id == ids[falla]:
            raise RuntimeError("detalle privado que nunca debe salir")
        return f"%PDF-{c.id}".encode()

    antes = (
        await db_session.execute(
            select(Comprobante.id, Comprobante.estado, Comprobante.cae)
        )
    ).all()
    await db_session.rollback()
    with patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante", side_effect=render
    ), patch("app.api.pdf.tempfile.TemporaryFile", side_effect=crear):
        r = await client.post("/api/pdf/zip", json={"ids": ids}, headers=auth_headers)
    assert temporales and all(t.closed for t in temporales)
    if falla is None:
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["access-control-expose-headers"] == "Content-Disposition"
        with ZipFile(BytesIO(r.content)) as z:
            assert z.testzip() is None
            assert len(z.namelist()) == len(set(z.namelist())) == 19
            assert {z.read(n) for n in z.namelist()} == {
                f"%PDF-{i}".encode() for i in ids
            }
    else:
        assert r.status_code == 409
        assert "content-disposition" not in r.headers
        assert r.json()["detail"]["fallidos"][0]["comprobante_id"] == ids[falla]
        assert "privado" not in r.text
    despues = (
        await db_session.execute(
            select(Comprobante.id, Comprobante.estado, Comprobante.cae)
        )
    ).all()
    assert antes == despues


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [[], [1, 1], [-1], [True], ["1"]])
async def test_zip_rechaza_seleccion_invalida(client, auth_headers, ids):
    r = await client.post("/api/pdf/zip", json={"ids": ids}, headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_zip_no_revela_ids_ajenos_ni_genera(
    client, auth_headers, db_session, test_empresa
):
    ids = await documentos(db_session, test_empresa.id, 1)
    with patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante", new_callable=AsyncMock
    ) as render:
        r = await client.post(
            "/api/pdf/zip", json={"ids": ids + [999999]}, headers=auth_headers
        )
    assert r.status_code == 404
    assert "fallidos" not in r.text
    render.assert_not_called()


@pytest.mark.asyncio
async def test_zip_revalida_revocacion_durante_render(
    client, auth_headers, db_session, test_empresa
):
    ids = await documentos(db_session, test_empresa.id, 1)

    async def revocar(*args):
        await db_session.execute(delete(UsuarioEmisorAcceso))
        await db_session.commit()
        return b"%PDF-test"

    with patch("app.api.pdf.pdf_service.generar_pdf_comprobante", side_effect=revocar):
        r = await client.post("/api/pdf/zip", json={"ids": ids}, headers=auth_headers)
    assert r.status_code == 403
    assert "content-disposition" not in r.headers


@pytest.mark.asyncio
async def test_zip_no_autorizado_no_recibe_pdf(
    client, auth_headers, db_session, test_empresa
):
    c = await _crear_comprobante_pdf(db_session, test_empresa.id)
    with patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante", new_callable=AsyncMock
    ) as render:
        r = await client.post(
            "/api/pdf/zip", json={"ids": [c.id]}, headers=auth_headers
        )
    assert r.status_code == 409
    render.assert_not_called()


@pytest.mark.asyncio
async def test_zip_colisiones_y_fallo_de_recursos(
    client, auth_headers, db_session, test_empresa
):
    ids = await documentos(db_session, test_empresa.id, 2)
    with patch("app.api.pdf._nombre_pdf", return_value="Comprobante.pdf"), patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante",
        new_callable=AsyncMock,
        return_value=b"%PDF-test",
    ):
        response = await client.post(
            "/api/pdf/zip", json={"ids": ids}, headers=auth_headers
        )
    with ZipFile(BytesIO(response.content)) as z:
        assert z.namelist() == ["Comprobante.pdf", f"Comprobante_{ids[1]}.pdf"]
    with patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante",
        new_callable=AsyncMock,
        side_effect=OSError("ruta privada"),
    ):
        response = await client.post(
            "/api/pdf/zip", json={"ids": ids}, headers=auth_headers
        )
    assert response.status_code == 503
    assert "privada" not in response.text
    assert "fallidos" not in response.text


@pytest.mark.asyncio
async def test_temporal_se_cierra_si_falla_la_transferencia():
    archivo = tempfile.TemporaryFile("w+b")
    archivo.write(b"ZIP-sintetico")
    response = _ZIPTemporal(archivo, 1)

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        raise OSError("desconexion sintetica")

    with pytest.raises(Exception):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert archivo.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("cobertura", ["completa", "ausente", "invalida"])
async def test_zip_historia_real_y_mismo_pdf_que_individual(
    client,
    auth_headers,
    db_session,
    test_empresa,
    monkeypatch,
    cobertura,
):
    comps, punto = await crear_historia(db_session, test_empresa, monkeypatch)
    ids = [c.id for c in comps]
    if cobertura != "completa":
        valores = (
            {"evidencia_hash": "0" * 64}
            if cobertura == "invalida"
            else {
                "evidencia_version": None,
                "evidencia_hash": None,
                "evidencia_json": None,
            }
        )
        await db_session.execute(update(IntentoEmisionFiscal).values(**valores))
    punto.numero = 99
    await db_session.commit()
    r = await client.post("/api/pdf/zip", json={"ids": ids}, headers=auth_headers)
    if cobertura == "invalida":
        assert r.status_code == 409
        assert len(r.json()["detail"]["fallidos"]) == len(ids)
        return
    assert r.status_code == 200
    individual = await client.get(
        f"/api/pdf/comprobante/{ids[0]}", headers=auth_headers
    )
    with ZipFile(BytesIO(r.content)) as z:
        texto_zip = " ".join(
            p.extract_text() for p in PdfReader(BytesIO(z.read(z.namelist()[0]))).pages
        )
        texto_individual = " ".join(
            p.extract_text() for p in PdfReader(BytesIO(individual.content)).pages
        )
        assert texto_zip == texto_individual
        assert (
            "snapshot" not in texto_zip.lower()
            and "Cotización conservada" not in texto_zip
        )
        assert ("0005" if cobertura == "completa" else "0099") in texto_zip


@pytest.mark.asyncio
async def test_zip_19_nativos_no_bloquea_event_loop(
    client, auth_headers, db_session, test_empresa
):
    ids = await documentos(db_session, test_empresa.id, 19)
    ticks = []
    terminado = asyncio.Event()

    async def heartbeat():
        while not terminado.is_set():
            ticks.append(perf_counter())
            await asyncio.sleep(0.01)

    tarea = asyncio.create_task(heartbeat())
    inicio = perf_counter()
    try:
        r = await client.post("/api/pdf/zip", json={"ids": ids}, headers=auth_headers)
    finally:
        terminado.set()
        await tarea
    assert r.status_code == 200
    with ZipFile(BytesIO(r.content)) as z:
        assert len(z.namelist()) == 19
        assert all(len(PdfReader(BytesIO(z.read(n))).pages) == 1 for n in z.namelist())
    assert len(ticks) > 10
    max_gap = max(b - a for a, b in zip(ticks, ticks[1:]))
    assert (
        max_gap < 2
    )  # A full native ZIP must not occupy the loop for its entire render.
    print(
        f"ZIP nativo: count=19 bytes={len(r.content)} seconds={perf_counter()-inicio:.2f} max_loop_gap={max_gap:.3f}"
    )
