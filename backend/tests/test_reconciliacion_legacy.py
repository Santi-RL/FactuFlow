"""Recuperación legacy real con datos sintéticos y consulta de lectura."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.arca.exceptions import ArcaServiceError
from app.arca.models import CbteAsocItem, IvaItem, TributoItem
from app.arca.models import ComprobanteResponse as ConsultaArca
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteGrupo,
    LoteComprobanteFila,
)
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.lote_comprobantes_service import (
    LoteComprobantesService,
    LoteComprobanteError,
)

CAE = "00000000000000"


async def crear_escenario_legacy(db_session, test_empresa):
    punto = PuntoVenta(
        empresa_id=test_empresa.id,
        numero=1,
        nombre="Sintético",
        activo=True,
        es_webservice=True,
    )
    lote = LoteComprobante(
        empresa_id=test_empresa.id,
        nombre_archivo="sintetico.xlsx",
        archivo_hash="a" * 64,
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
    )
    db_session.add_all([punto, lote])
    await db_session.flush()
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto.id,
        tipo_comprobante=6,
        concepto=2,
        fecha_emision=date(2026, 8, 5),
        confirmacion_fecha_fiscal=True,
        fecha_servicio_desde=date(2026, 8, 1),
        fecha_servicio_hasta=date(2026, 8, 5),
        fecha_vto_pago=date(2026, 8, 10),
        tipo_documento=99,
        numero_documento="0",
        razon_social="Receptor sintético",
        condicion_iva="CF",
        guardar_cliente=False,
        items=[
            ItemComprobanteCreate(
                descripcion="Servicio sintético",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("21"),
            )
        ],
    )
    payload = request.model_dump(mode="json")
    grupo = LoteComprobanteGrupo(
        empresa_id=test_empresa.id,
        lote_id=lote.id,
        comprobante_ref="SINTETICO",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=1,
        payload_json=payload,
        total_estimado=Decimal("1210"),
    )
    db_session.add(grupo)
    await db_session.flush()
    fila = LoteComprobanteFila(
        lote_id=lote.id,
        grupo_id=grupo.id,
        fila_excel=2,
        comprobante_ref="SINTETICO",
        estado="validado",
        datos_json={},
    )
    db_session.add(fila)
    intento = IntentoEmisionFiscal(
        empresa_id=test_empresa.id,
        punto_venta_id=punto.id,
        punto_venta_numero=1,
        tipo_comprobante=6,
        numero_planificado=1,
        fecha_emision=date(2026, 8, 5),
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        total=Decimal("1210"),
        payload_hash=IdempotenciaFiscalService.calcular_payload_hash(
            IdempotenciaFiscalService.payload_sin_confirmacion_duplicado(payload)
        ),
        huella_logica="h" * 64,
        estado="en_proceso",
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add(intento)
    await db_session.commit()
    consulta = SimpleNamespace(
        resultado="A",
        emision_tipo="CAE",
        cae=CAE,
        cae_vencimiento="20260819",
        cuit_emisor=test_empresa.cuit,
        punto_venta=1,
        tipo_cbte=6,
        numero=1,
        cbte_desde=1,
        cbte_hasta=1,
        fecha_cbte="20260805",
        concepto=2,
        tipo_doc=99,
        nro_doc=0,
        condicion_iva_receptor_id=5,
        imp_total=Decimal("1210"),
        imp_neto=Decimal("1000"),
        imp_iva=Decimal("210"),
        imp_op_ex=Decimal("0"),
        imp_tot_conc=Decimal("0"),
        imp_trib=Decimal("0"),
        moneda_id="PES",
        moneda_cotiz=Decimal("1"),
        fecha_serv_desde="20260801",
        fecha_serv_hasta="20260805",
        fecha_vto_pago="20260810",
        iva=[IvaItem(id=5, base_imp=Decimal("1000"), importe=Decimal("210"))],
        tributos=None,
        cbtes_asoc=None,
        adicionales_presentes=[],
    )
    return SimpleNamespace(
        db=db_session,
        service=FacturacionService(db_session),
        punto=punto,
        lote=lote,
        grupo=grupo,
        fila=fila,
        intento=intento,
        request=request,
        consulta=consulta,
        payload=deepcopy(payload),
    )


@pytest.fixture
async def legacy(db_session, test_empresa):
    return await crear_escenario_legacy(db_session, test_empresa)


async def reconciliar(escenario, durante_consulta=None):
    class WSFE:
        consultas = 0

        async def fe_comp_consultar(self, **kwargs):
            self.consultas += 1
            assert kwargs == {
                "punto_venta": 1,
                "tipo_cbte": escenario.intento.tipo_comprobante,
                "numero": 1,
            }
            if durante_consulta:
                await durante_consulta()
            return escenario.consulta

        async def fe_cae_solicitar(self, *args, **kwargs):
            raise AssertionError("La recuperación nunca solicita CAE")

    cliente = WSFE()
    resultado = await escenario.service._reconciliar_intento_stale(
        intento=escenario.intento, wsfe_client=cliente, punto_venta_numero=1
    )
    await escenario.db.refresh(escenario.intento)
    await escenario.db.refresh(escenario.grupo)
    assert cliente.consultas == 1
    assert escenario.grupo.payload_json == escenario.payload
    return resultado


@pytest.mark.asyncio
async def test_legacy_reconstruye_coincidencia_y_cierra_filas(legacy):
    assert await reconciliar(legacy) is None
    comprobante = await legacy.db.get(Comprobante, legacy.intento.comprobante_id)
    assert comprobante.total == Decimal("1210")
    assert comprobante.iva_21 == Decimal("210")
    assert comprobante.moneda == "PES"
    assert legacy.intento.estado == "autorizado"
    assert legacy.grupo.estado == "autorizado"
    await legacy.db.refresh(legacy.fila)
    assert legacy.fila.estado == "autorizado"
    replay = await legacy.service._respuesta_desde_intento_resuelto(legacy.intento)
    assert replay.exito and replay.comprobante_id == comprobante.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("moneda_id", "DOL"),
        ("moneda_cotiz", Decimal("1.000000000001")),
        ("imp_neto", Decimal("1210")),
        ("imp_iva", Decimal("0")),
        ("imp_op_ex", Decimal("100")),
        ("imp_tot_conc", Decimal("100")),
        ("imp_trib", Decimal("1")),
        ("concepto", 3),
        ("condicion_iva_receptor_id", 6),
        ("fecha_serv_desde", "20260802"),
        ("fecha_serv_hasta", "20260806"),
        ("fecha_vto_pago", "20260811"),
        ("cbte_hasta", 2),
        ("iva", [IvaItem(id=4, base_imp=Decimal("2000"), importe=Decimal("210"))]),
        ("cbtes_asoc", [CbteAsocItem(tipo=6, punto_venta=1, numero=2)]),
        (
            "tributos",
            [
                TributoItem(
                    id=99,
                    descripcion="Sintético",
                    base_imp=Decimal("1"),
                    alic=Decimal("1"),
                    importe=Decimal("1"),
                )
            ],
        ),
        ("adicionales_presentes", ["PeriodoAsoc"]),
    ],
)
async def test_legacy_diferencia_con_igual_total_conserva_cae_y_reserva(
    legacy, campo, valor
):
    setattr(legacy.consulta, campo, valor)
    resultado = await reconciliar(legacy)
    assert resultado is legacy.intento
    assert legacy.intento.estado == "requiere_reconciliacion"
    assert legacy.intento.categoria_error == "arca_consulta_inconsistente"
    assert legacy.intento.cae == CAE
    assert legacy.intento.cae_vencimiento == date(2026, 8, 19)
    assert legacy.intento.comprobante_id is None
    assert legacy.grupo.estado == "validado"
    assert list(await legacy.db.scalars(select(Comprobante))) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("imp_neto", None),
        ("moneda_cotiz", None),
        ("concepto", None),
        ("iva", None),
        ("fecha_serv_hasta", None),
        ("moneda_cotiz", Decimal("NaN")),
    ],
)
async def test_legacy_consulta_incompleta_no_inventa_coincidencia(legacy, campo, valor):
    setattr(legacy.consulta, campo, valor)
    await reconciliar(legacy)
    assert legacy.intento.categoria_error == "arca_consulta_incompleta"
    assert legacy.intento.cae == CAE
    assert legacy.intento.estado == "requiere_reconciliacion"
    assert legacy.intento.comprobante_id is None


@pytest.mark.asyncio
async def test_legacy_condicion_no_devuelta_conserva_cobertura_antigua(legacy):
    legacy.consulta.condicion_iva_receptor_id = None
    assert await reconciliar(legacy) is None
    assert legacy.intento.estado == "autorizado"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("cuit_emisor", "20999999999"),
        ("numero", 2),
        ("punto_venta", 2),
        ("tipo_cbte", 11),
        ("emision_tipo", "CAEA"),
    ],
)
async def test_legacy_no_atribuye_codigo_de_otro_scope(legacy, campo, valor):
    setattr(legacy.consulta, campo, valor)
    await reconciliar(legacy)
    assert legacy.intento.cae is None
    assert legacy.intento.estado == "requiere_reconciliacion"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("tipo_doc", 96),
        ("nro_doc", 12345678),
        ("fecha_cbte", "20260806"),
        ("imp_total", "NaN"),
    ],
)
async def test_legacy_diferencia_identidad_fiscal_conserva_autorizacion_del_numero(
    legacy, campo, valor
):
    setattr(legacy.consulta, campo, valor)
    await reconciliar(legacy)
    assert legacy.intento.cae == CAE
    assert legacy.intento.categoria_error == (
        "arca_consulta_incompleta" if valor == "NaN" else "arca_consulta_inconsistente"
    )


@pytest.mark.asyncio
async def test_legacy_payload_modificado_no_se_repara_para_hacerlo_coincidir(legacy):
    modificado = deepcopy(legacy.payload)
    modificado["moneda"] = "DOL"
    legacy.grupo.payload_json = modificado
    legacy.payload = deepcopy(modificado)
    await legacy.db.commit()
    await reconciliar(legacy)
    assert legacy.intento.categoria_error == "arca_consulta_inconsistente"
    assert legacy.intento.cae == CAE


@pytest.mark.asyncio
async def test_legacy_sin_payload_con_cae_conocido_no_reemite(legacy):
    legacy.intento.grupo_id = None
    legacy.intento.lote_id = None
    await legacy.db.commit()
    await reconciliar(legacy)
    assert legacy.intento.categoria_error == "arca_autorizado_sin_payload_local"
    assert legacy.intento.cae == CAE
    assert legacy.intento.comprobante_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "alterar", [None, "moneda", "subtotal", "receptor_condicion_iva"]
)
async def test_legacy_comprobante_parcial_compara_snapshot_sin_cliente_actual(
    legacy, alterar
):
    comprobante = await legacy.service._guardar_comprobante(
        legacy.request,
        1,
        legacy.service._calcular_totales(legacy.request.items),
        legacy.consulta,
        legacy.punto,
        commit=False,
    )
    legacy.intento.grupo_id = None
    legacy.intento.lote_id = None
    if alterar:
        setattr(
            comprobante,
            alterar,
            {
                "moneda": "DOL",
                "subtotal": Decimal("999"),
                "receptor_condicion_iva": "MT",
            }[alterar],
        )
    await legacy.db.commit()
    resultado = await reconciliar(legacy)
    if alterar is None:
        assert resultado is None
        assert legacy.intento.comprobante_id == comprobante.id
        assert legacy.intento.estado == "autorizado"
    else:
        assert legacy.intento.estado == "requiere_reconciliacion"
        assert legacy.intento.comprobante_id is None
    assert len(list(await legacy.db.scalars(select(Comprobante)))) == 1


@pytest.mark.asyncio
async def test_legacy_respuesta_tardia_no_sobrescribe_intento_terminal(legacy):
    async def resolver_antes_de_responder():
        legacy.intento.estado = "requiere_reconciliacion"
        legacy.intento.mensaje = "Otro proceso conservó la evidencia."
        await legacy.db.commit()

    await reconciliar(legacy, resolver_antes_de_responder)
    assert legacy.intento.mensaje == "Otro proceso conservó la evidencia."
    assert legacy.intento.cae is None


@pytest.mark.asyncio
async def test_legacy_no_existe_no_borra_cae_ya_conocido(legacy):
    legacy.intento.cae = CAE
    legacy.intento.cae_vencimiento = date(2026, 8, 19)
    await legacy.db.commit()

    class WSFE:
        async def fe_comp_consultar(self, **kwargs):
            raise ArcaServiceError("Comprobante inexistente", codigo="602")

    await legacy.service._reconciliar_intento_stale(
        intento=legacy.intento, wsfe_client=WSFE(), punto_venta_numero=1
    )
    await legacy.db.refresh(legacy.intento)
    assert legacy.intento.estado == "requiere_reconciliacion"
    assert legacy.intento.cae == CAE


@pytest.mark.asyncio
async def test_legacy_cae_contradictorio_conserva_evidencia_anterior(legacy):
    legacy.intento.cae = "11111111111111"
    legacy.intento.cae_vencimiento = date(2026, 8, 20)
    await legacy.db.commit()
    await reconciliar(legacy)
    assert legacy.intento.cae == "11111111111111"
    assert legacy.intento.cae_vencimiento == date(2026, 8, 20)
    assert legacy.intento.categoria_error == "arca_consulta_inconsistente"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("empresa_id", 999),
        ("punto_venta_id", 999),
        ("cotizacion", None),
        ("numero_documento", ""),
    ],
)
async def test_legacy_payload_de_otro_scope_o_incompleto_no_reconstruye(
    legacy, campo, valor
):
    payload = deepcopy(legacy.payload)
    if valor is None:
        payload.pop(campo)
    else:
        payload[campo] = valor
    legacy.grupo.payload_json = payload
    legacy.payload = deepcopy(payload)
    legacy.intento.payload_hash = IdempotenciaFiscalService.calcular_payload_hash(
        IdempotenciaFiscalService.payload_sin_confirmacion_duplicado(payload)
    )
    await legacy.db.commit()
    await reconciliar(legacy)
    assert legacy.intento.estado == "requiere_reconciliacion"
    assert legacy.intento.cae == CAE
    assert legacy.intento.comprobante_id is None


@pytest.mark.asyncio
async def test_legacy_mismo_cae_con_otro_vencimiento_no_borra_evidencia(legacy):
    legacy.intento.cae = CAE
    legacy.intento.cae_vencimiento = date(2026, 8, 20)
    await legacy.db.commit()
    await reconciliar(legacy)
    assert legacy.intento.cae_vencimiento == date(2026, 8, 20)
    assert legacy.intento.categoria_error == "arca_consulta_inconsistente"


@pytest.mark.asyncio
async def test_legacy_adaptador_real_con_respuesta_incompleta_preserva_cae(legacy):
    from tests.test_arca.test_wsfe_consulta import respuesta_soap
    from tests.test_arca.test_wsfev1 import _crear_cliente_wsfe

    result = respuesta_soap()
    result.CbteDesde = result.CbteHasta = 1
    result.ImpTotal = Decimal("1210")
    result.ImpIVA = Decimal("210")
    delattr(result, "ImpNeto")

    class SOAP:
        def FECompConsultar(self, **kwargs):
            return SimpleNamespace(ResultGet=result, Errors=None)

    await legacy.service._reconciliar_intento_stale(
        intento=legacy.intento,
        wsfe_client=_crear_cliente_wsfe(SOAP()),
        punto_venta_numero=1,
    )
    await legacy.db.refresh(legacy.intento)
    assert legacy.intento.estado == "requiere_reconciliacion"
    assert legacy.intento.cae == CAE
    assert legacy.intento.comprobante_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("categoria", ["c", "cero", "varias", "nota"])
async def test_legacy_recupera_categorias_originales_y_orden_de_iva(legacy, categoria):
    payload = deepcopy(legacy.payload)
    if categoria == "c":
        payload["tipo_comprobante"] = 11
    if categoria in {"c", "cero"}:
        payload["items"][0]["iva_porcentaje"] = "0"
        legacy.consulta.imp_total = legacy.consulta.imp_neto = Decimal("1000")
        legacy.consulta.imp_iva = Decimal("0")
        legacy.consulta.iva = (
            None
            if categoria == "c"
            else [IvaItem(id=3, base_imp=Decimal("1000"), importe=Decimal("0"))]
        )
    elif categoria == "varias":
        payload["items"] = [
            dict(payload["items"][0], iva_porcentaje=tasa)
            for tasa in ("21", "10.5", "27")
        ]
        legacy.consulta.imp_neto = Decimal("3000")
        legacy.consulta.imp_iva = Decimal("585")
        legacy.consulta.imp_total = Decimal("3585")
        legacy.consulta.iva = [
            IvaItem(id=id_iva, base_imp=Decimal("1000"), importe=Decimal(importe))
            for id_iva, importe in ((6, "270"), (4, "105"), (5, "210"))
        ]
    else:
        payload["tipo_comprobante"] = 8
        payload["comprobantes_asociados"] = [
            {
                "tipo_comprobante": 6,
                "punto_venta": 1,
                "numero": 99,
                "fecha": "2026-08-01",
                "cuit": "20123456789",
            }
        ]
        legacy.consulta.cbtes_asoc = [
            CbteAsocItem(
                tipo=6,
                punto_venta=1,
                numero=99,
                fecha_cbte="20260801",
                cuit="20123456789",
            )
        ]
    legacy.grupo.payload_json = payload
    legacy.payload = deepcopy(payload)
    legacy.intento.payload_hash = IdempotenciaFiscalService.calcular_payload_hash(
        IdempotenciaFiscalService.payload_sin_confirmacion_duplicado(payload)
    )
    legacy.intento.total = legacy.consulta.imp_total
    legacy.intento.tipo_comprobante = payload["tipo_comprobante"]
    legacy.grupo.tipo_comprobante = payload["tipo_comprobante"]
    legacy.consulta.tipo_cbte = payload["tipo_comprobante"]
    await legacy.db.commit()
    assert await reconciliar(legacy) is None
    assert legacy.intento.estado == "autorizado"


@pytest.mark.asyncio
async def test_legacy_grupo_resuelto_durante_consulta_conserva_su_estado(legacy):
    async def descartar():
        legacy.grupo.estado = "descartado"
        await legacy.db.commit()

    await reconciliar(legacy, descartar)
    assert legacy.grupo.estado == "descartado"
    assert legacy.intento.estado == "requiere_reconciliacion"
    assert legacy.intento.cae == CAE


@pytest.mark.asyncio
async def test_legacy_mismo_total_con_otro_desglose_fiscal_coherente(legacy):
    legacy.consulta.imp_neto = Decimal("1210")
    legacy.consulta.imp_iva = Decimal("0")
    legacy.consulta.iva = [
        IvaItem(id=3, base_imp=Decimal("1210"), importe=Decimal("0"))
    ]
    await reconciliar(legacy)
    assert legacy.intento.categoria_error == "arca_consulta_inconsistente"
    assert legacy.intento.cae == CAE
    assert legacy.intento.comprobante_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("parcial", [False, True])
async def test_consulta_externa_conserva_exigencia_de_datos_basicos_completos(
    legacy, test_empresa, parcial
):
    request = legacy.request.model_copy(
        update={"tipo_documento": 96, "numero_documento": "12345678"}
    )
    datos = vars(legacy.consulta).copy()
    datos.update(tipo_doc=96, nro_doc=12345678, fecha_proceso="20260805120000")
    if parcial:
        datos["imp_neto"] = None
    consulta = ConsultaArca.model_validate(datos)
    item = {
        "fecha_emision": "2026-08-05",
        "total": "1210.00",
        "cae": CAE,
        "tipo_comprobante": 6,
        "punto_venta_numero": 1,
        "numero": 1,
    }
    servicio = LoteComprobantesService(legacy.db)
    if parcial:
        with pytest.raises(LoteComprobanteError, match="incompletos"):
            servicio._validar_consulta_arca_externa(
                test_empresa, legacy.grupo, request, item, consulta
            )
    else:
        servicio._validar_consulta_arca_externa(
            test_empresa, legacy.grupo, request, item, consulta
        )
