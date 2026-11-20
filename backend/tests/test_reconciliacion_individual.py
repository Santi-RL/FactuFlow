"""Recuperación individual después de autorizar en ARCA y perder la respuesta."""

from datetime import date
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from sqlalchemy import delete, func, select

from app.arca.exceptions import ArcaServiceError
from app.arca.models import CAEResponse, ComprobanteResponse
from app.core.config import settings
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.elegibilidad_rece import PuntoVentaGuardaEmisionRece
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from app.schemas.comprobante import ComprobanteAsociadoCreate
from app.services.facturacion_service import FacturacionService
from app.services.lecturas_historicas_service import proyectar_original
from tests.test_evidencia_fiscal import _request
from tests.test_facturacion_service import (
    _crear_operacion_rece_sintetica,
    _fijar_reloj_facturacion,
)

CAE_PRUEBA = "12345678901234"
VENCIMIENTO_PRUEBA = "20260818"


class CorteDelProceso(BaseException):
    """Simula que el proceso desaparece, incluso antes de manejar excepciones."""


class ArcaSimulada:
    def __init__(self, cuit):
        self.cuit = cuit
        self.config = SimpleNamespace(ambiente="produccion")
        self.emitidos = []
        self.consultas = 0
        self.variacion = None

    async def fe_param_get_ptos_venta(self):
        return [SimpleNamespace(numero=5, bloqueado="N", emision_tipo="CAE")]

    async def fe_comp_ultimo_autorizado(self, *_args):
        return 0

    async def fe_cae_solicitar(self, solicitud):
        self.emitidos.append(solicitud)
        return CAEResponse(
            cae=CAE_PRUEBA,
            cae_vencimiento=VENCIMIENTO_PRUEBA,
            numero_comprobante=solicitud.cbte_desde,
            tipo_cbte=solicitud.tipo_cbte,
            punto_venta=solicitud.punto_venta,
            resultado="A",
        )

    async def fe_comp_consultar(self, *, punto_venta, tipo_cbte, numero):
        self.consultas += 1
        [original] = self.emitidos
        assert (punto_venta, tipo_cbte, numero) == (
            original.punto_venta,
            original.tipo_cbte,
            original.cbte_desde,
        )
        consulta = ComprobanteResponse(
            **original.model_dump(),
            numero=numero,
            cuit_emisor=self.cuit,
            resultado="A",
            emision_tipo="CAE",
            cae=CAE_PRUEBA,
            cae_vencimiento=VENCIMIENTO_PRUEBA,
        )
        if self.variacion == "no_encontrado":
            raise ArcaServiceError("Comprobante no encontrado", codigo="602")
        if self.variacion == "asociado_distinto":
            consulta.cbtes_asoc[0].numero += 1
        if self.variacion == "iva_ausente":
            consulta.imp_iva = None
        if self.variacion == "cae_contradictorio":
            consulta.cae = "23456789012345"
        if self.variacion == "atributos_opcionales":
            consulta.condicion_iva_receptor_id = None
            consulta.cbte_desde = consulta.cbte_hasta = None
            consulta.cbtes_asoc[0].fecha_cbte = consulta.cbtes_asoc[0].cuit = None
        return consulta


async def autorizar_y_perder_respuesta(db, empresa, monkeypatch, *, publicada=False):
    _fijar_reloj_facturacion(monkeypatch)
    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(settings, "fiscal_attempt_stale_minutes", 0)
    punto = PuntoVenta(
        numero=5,
        activo=True,
        es_webservice=True,
        empresa_id=empresa.id,
        revision_fiscal=1,
    )
    db.add(punto)
    await db.commit()
    request = _request(empresa.id, punto.id).model_copy(
        update={
            "tipo_comprobante": 8,
            "guardar_cliente": True,
            "comprobantes_asociados": [
                ComprobanteAsociadoCreate(
                    tipo_comprobante=6,
                    punto_venta=5,
                    numero=17,
                    cuit=empresa.cuit,
                    fecha=date(2026, 8, 1),
                )
            ],
        }
    )
    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db, empresa=empresa, punto_venta=punto, requests=[request], batch=False
    )
    arca = ArcaSimulada(empresa.cuit)

    async def cliente(*_args):
        return arca

    async def certificado(*_args):
        return SimpleNamespace()

    async def interrumpir(*_args, **_kwargs):
        if publicada:
            raise RuntimeError("Persistencia interrumpida")
        raise CorteDelProceso()

    monkeypatch.setattr(FacturacionService, "_obtener_cliente_wsfe", cliente)
    monkeypatch.setattr(FacturacionService, "_obtener_certificado_activo", certificado)
    operacion_id, clave = operacion.id, operacion.idempotency_key
    with monkeypatch.context() as patch:
        patch.setattr(FacturacionService, "_guardar_comprobante", interrumpir)
        service = FacturacionService(db)
        if publicada:
            respuesta = await service.emitir_comprobante(
                request, operacion_id=operacion_id, contexto_rece=contexto
            )
            assert respuesta.requiere_reconciliacion
            operacion = await db.get(OperacionIdempotente, operacion_id)
            operacion.response_json = respuesta.model_dump(mode="json")
            await db.commit()
        else:
            with pytest.raises(CorteDelProceso):
                await service.emitir_comprobante(
                    request, operacion_id=operacion_id, contexto_rece=contexto
                )
        await db.rollback()
    assert len(arca.emitidos) == 1
    return operacion_id, clave, arca


@pytest.mark.parametrize("publicada", [False, True])
async def test_verificar_recupera_nota_y_replay_desde_comprobantes(
    db_session, test_empresa, auth_headers, client, monkeypatch, publicada
):
    operacion_id, clave, arca = await autorizar_y_perder_respuesta(
        db_session, test_empresa, monkeypatch, publicada=publicada
    )
    arca.variacion = "atributos_opcionales"
    pendientes = await client.get(
        "/api/comprobantes/emisiones-pendientes", headers=auth_headers
    )
    assert pendientes.status_code == 200
    assert [item["operacion_id"] for item in pendientes.json()] == [operacion_id]

    primera = await client.post(
        "/api/comprobantes/verificar-emision",
        params={"operacion_id": operacion_id},
        headers=auth_headers,
    )
    assert primera.status_code == 200, primera.text
    assert primera.json()["exito"] is True, primera.text
    assert primera.json()["cae"] == CAE_PRUEBA
    segunda = await client.post(
        "/api/comprobantes/verificar-emision",
        headers={**auth_headers, "X-Idempotency-Key": clave},
    )
    assert segunda.json() == primera.json()
    assert len(arca.emitidos) == arca.consultas == 1
    assert await db_session.scalar(select(func.count(Cliente.id))) == 0
    assert await db_session.scalar(select(func.count(Comprobante.id))) == 1
    intento = await db_session.scalar(select(IntentoEmisionFiscal))
    assert intento.estado == "autorizado"
    assert intento.resultado_fiscal_at is None
    guarda = await db_session.get(PuntoVentaGuardaEmisionRece, intento.guarda_rece_id)
    assert guarda.fase == "cerrada_terminal"
    comprobante = await db_session.get(Comprobante, intento.comprobante_id)
    lectura = proyectar_original(comprobante, intento)
    assert lectura.comprobantes_asociados[0].numero == 17
    detalle = await client.get(
        f"/api/comprobantes/{comprobante.id}", headers=auth_headers
    )
    assert (
        detalle.json()["datos_historicos"]["comprobantes_asociados"][0]["numero"] == 17
    )
    pdf = await client.get(
        f"/api/pdf/comprobante/{comprobante.id}", headers=auth_headers
    )
    assert pdf.status_code == 200
    texto = " ".join(
        pagina.extract_text() for pagina in PdfReader(BytesIO(pdf.content)).pages
    )
    assert "00000017" in texto
    fecha = intento.fecha_emision
    for endpoint, parametros in (
        ("ventas", {"desde": fecha.isoformat(), "hasta": fecha.isoformat()}),
        ("iva-ventas", {"periodo_mes": fecha.month, "periodo_anio": fecha.year}),
    ):
        reporte = await client.get(
            f"/api/reportes/{endpoint}", params=parametros, headers=auth_headers
        )
        assert reporte.status_code == 200
        assert len(reporte.json()["comprobantes"]) == 1
    pendientes = await client.get(
        "/api/comprobantes/emisiones-pendientes", headers=auth_headers
    )
    assert pendientes.json() == []


@pytest.mark.parametrize(
    "variacion",
    ["no_encontrado", "asociado_distinto", "iva_ausente", "cae_contradictorio"],
)
async def test_verificar_conserva_reserva_ante_consulta_inconclusa(
    db_session, test_empresa, auth_headers, client, monkeypatch, variacion
):
    operacion_id, _, arca = await autorizar_y_perder_respuesta(
        db_session, test_empresa, monkeypatch, publicada=True
    )
    arca.variacion = variacion
    resultado = await client.post(
        "/api/comprobantes/verificar-emision",
        params={"operacion_id": operacion_id},
        headers=auth_headers,
    )
    assert resultado.status_code == 200
    assert resultado.json()["requiere_reconciliacion"] is True
    assert resultado.json()["cae"] == CAE_PRUEBA
    assert len(arca.emitidos) == arca.consultas == 1
    intento = await db_session.scalar(select(IntentoEmisionFiscal))
    assert intento.estado == "requiere_reconciliacion"
    assert await db_session.scalar(select(func.count(Comprobante.id))) == 0


async def test_revocar_acceso_durante_consulta_impide_cerrar_la_operacion(
    db_session, test_empresa, test_user, auth_headers, client, monkeypatch
):
    usuario_id = test_user.id
    operacion_id, _, arca = await autorizar_y_perder_respuesta(
        db_session, test_empresa, monkeypatch
    )
    consultar = arca.fe_comp_consultar

    async def consultar_y_revocar(**kwargs):
        resultado = await consultar(**kwargs)
        await db_session.execute(
            delete(UsuarioEmisorAcceso).where(
                UsuarioEmisorAcceso.usuario_id == usuario_id
            )
        )
        await db_session.commit()
        return resultado

    monkeypatch.setattr(arca, "fe_comp_consultar", consultar_y_revocar)
    respuesta = await client.post(
        "/api/comprobantes/verificar-emision",
        params={"operacion_id": operacion_id},
        headers=auth_headers,
    )
    assert respuesta.status_code == 404
    assert CAE_PRUEBA not in respuesta.text
    assert len(arca.emitidos) == arca.consultas == 1
    assert await db_session.scalar(select(func.count(Comprobante.id))) == 0
    intento = await db_session.scalar(select(IntentoEmisionFiscal))
    assert intento.estado == "en_proceso"
