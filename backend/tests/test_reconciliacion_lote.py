"""Casos donde una consulta de lote tiene que conservar la incertidumbre."""

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError

from app.models.comprobante import Comprobante
from app.models.elegibilidad_rece import PuntoVentaGuardaEmisionRece as Guarda
from app.models.idempotencia_fiscal import IntentoEmisionFiscal as Intento
from app.models.lote_comprobante import (
    LoteComprobante as Lote,
    LoteComprobanteEvento as Evento,
    LoteComprobanteGrupo as Grupo,
)
from app.models.usuario import Usuario
from app.services.reconciliacion_lote_service import ReconciliacionLoteService
from tests.integration.test_reconciliacion_lote_postgresql import preparar


@pytest.mark.parametrize(
    "fallo", ["sin_frontera", "iva", "cae_previo", "revocacion", "commit_ambiguo"]
)
async def test_conserva_evidencia_ante_fallo_de_recuperacion(
    db_session, monkeypatch, fallo
):
    db = db_session
    wsfe, params, ids = await preparar(db, monkeypatch)
    lote_id, _, usuario_id, _ = params
    consulta = wsfe.fe_comp_consultar
    if fallo == "sin_frontera":
        await db.execute(delete(Evento).where(Evento.accion == "frontera_envio_lote"))
    if fallo == "cae_previo":
        i = await db.scalar(select(Intento).where(Intento.grupo_id == ids[1]))
        i.cae = "90000000000002"
    await db.commit()

    async def simular(**kwargs):
        respuesta = await consulta(**kwargs)
        if fallo == "iva":
            respuesta.imp_iva = None
        if fallo == "revocacion":
            (await db.get(Usuario, usuario_id)).activo = False
            await db.commit()
        return respuesta

    monkeypatch.setattr(wsfe, "fe_comp_consultar", simular)
    if fallo == "commit_ambiguo":
        commit = db.commit
        pendiente = True

        async def perder_confirmacion():
            nonlocal pendiente
            await commit()
            if pendiente:
                pendiente = False
                raise OperationalError("COMMIT", {}, RuntimeError("Respuesta perdida"))

        monkeypatch.setattr(db, "commit", perder_confirmacion)
    servicio = ReconciliacionLoteService(db)
    if fallo == "revocacion":
        with pytest.raises(PermissionError):
            await servicio.verificar(*params)
    else:
        resumen = await servicio.verificar(*params)
        assert resumen.sin_enviar == (0 if fallo == "sin_frontera" else 1)
        assert resumen.autorizados == (
            2 if fallo in {"sin_frontera", "commit_ambiguo"} else 1
        )
    assert (await db.get(Lote, lote_id)).estado == "requiere_reconciliacion"
    assert (await db.get(Grupo, ids[3])).estado == "requiere_reconciliacion"
    assert await db.scalar(select(func.count(Comprobante.id))) == (
        2 if fallo in {"sin_frontera", "commit_ambiguo"} else 1
    )
    i = await db.scalar(select(Intento).where(Intento.grupo_id == ids[1]))
    assert (await db.get(Guarda, i.guarda_rece_id)).fase == "requiere_reconciliacion"
    if fallo == "cae_previo":
        assert i.cae == "90000000000002"
    assert len(wsfe.enviados) == 3


async def test_api_recupera_pdf_e_informes_con_otra_fila_pendiente(
    db_session, client, admin_auth_headers, monkeypatch
):
    wsfe, (lote_id, empresa_id, _, op_id), ids = await preparar(db_session, monkeypatch)
    headers = {**admin_auth_headers, "X-Empresa-Id": str(empresa_id)}
    ruta = f"/api/lotes-comprobantes/{lote_id}"
    verificada = await client.post(
        ruta + "/verificar-estado", params={"operacion_id": op_id}, headers=headers
    )
    assert verificada.status_code == 200, verificada.text
    assert verificada.json()["pendientes"] == 1
    i = await db_session.scalar(select(Intento).where(Intento.grupo_id == ids[1]))
    comprobante_id, fecha = i.comprobante_id, i.fecha_emision
    original = await client.get(f"/api/comprobantes/{comprobante_id}", headers=headers)
    assert original.status_code == 200 and original.json()["numero"] == 2
    pdf = await client.get(f"/api/pdf/comprobante/{comprobante_id}", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    for nombre, filtros in (
        ("ventas", {"desde": fecha.isoformat(), "hasta": fecha.isoformat()}),
        ("iva-ventas", {"periodo_mes": fecha.month, "periodo_anio": fecha.year}),
    ):
        reporte = await client.get(
            f"/api/reportes/{nombre}", headers=headers, params=filtros
        )
        assert reporte.status_code == 200
        assert len(reporte.json()["comprobantes"]) == 2
    externo = await client.post(
        ruta + "/reconciliar-externos",
        headers=headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": ids[2],
                    "tipo_comprobante": 6,
                    "punto_venta_numero": 5,
                    "numero": 3,
                    "fecha_emision": fecha.isoformat(),
                    "total": "1210",
                    "motivo": "Caso sintético",
                }
            ]
        },
    )
    assert externo.status_code == 400 and "Verificar estado" in externo.json()["detail"]
    assert len(wsfe.enviados) == 3
