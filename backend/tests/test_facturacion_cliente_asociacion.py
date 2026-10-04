"""La asociación administrativa no altera el comprobante fiscal autorizado."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.models import CAEResponse
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.lote_comprobantes_service import LoteComprobantesService
from tests.test_facturacion_service import (
    FECHA_FISCAL_PRUEBA,
    _crear_operacion_rece_sintetica,
    _fijar_reloj_facturacion,
)


CAE_SINTETICO = "00000000000000"
VENCIMIENTO_CAE_SINTETICO = "20260819"


@pytest.fixture(autouse=True)
def _usar_reloj_y_ambiente_sinteticos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija el reloj y el ambiente de los dobles, sin acceder a ARCA."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    _fijar_reloj_facturacion(monkeypatch)


@pytest.fixture
async def escenario_cliente(
    db_session: AsyncSession, test_empresa: Empresa
) -> tuple[FacturacionService, EmitirComprobanteRequest, PuntoVenta]:
    """Prepara un receptor identificado y un punto de venta persistido."""
    punto = PuntoVenta(
        empresa_id=test_empresa.id,
        numero=1,
        nombre="Punto sintético",
        activo=True,
        es_webservice=True,
    )
    db_session.add(punto)
    await db_session.commit()
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        confirmacion_fecha_fiscal=True,
        tipo_documento=96,
        numero_documento="12345678",
        razon_social="Receptor fiscal sintético",
        condicion_iva="CF",
        domicilio="Domicilio fiscal sintético",
        guardar_cliente=True,
        items=[
            ItemComprobanteCreate(
                codigo="SINTETICO",
                descripcion="Producto sintético",
                cantidad=Decimal("2"),
                precio_unitario=Decimal("500"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    return FacturacionService(db_session), request, punto


async def _agregar_clientes(
    db: AsyncSession,
    empresa_id: int,
    cantidad: int,
    *,
    tipo_documento: str = "DNI",
) -> list[Cliente]:
    """Crea registros administrativos distintos del snapshot del receptor."""
    clientes = [
        Cliente(
            empresa_id=empresa_id,
            tipo_documento=tipo_documento,
            numero_documento="12345678",
            razon_social=f"Registro administrativo sintético {indice}",
            condicion_iva="Monotributo",
            domicilio="Otro domicilio sintético",
        )
        for indice in range(cantidad)
    ]
    db.add_all(clientes)
    await db.commit()
    return clientes


async def _guardar_sintetico(service, request, punto, *, commit=False):
    """Persiste una autorización sintética sin WSAA ni solicitud de CAE."""
    return await service._guardar_comprobante(
        request=request,
        numero=1,
        totales=service._calcular_totales(request.items),
        resultado_arca=SimpleNamespace(
            cae=CAE_SINTETICO,
            cae_vencimiento=VENCIMIENTO_CAE_SINTETICO,
        ),
        punto_venta=punto,
        commit=commit,
    )


def _comprobar_snapshot(comprobante: Comprobante, request) -> None:
    """Comprueba hechos fiscales sin tomar datos del cliente administrativo."""
    assert comprobante.receptor_tipo_documento == request.tipo_documento
    assert comprobante.receptor_numero_documento == request.numero_documento
    assert comprobante.receptor_razon_social == request.razon_social
    assert comprobante.receptor_condicion_iva == request.condicion_iva
    assert comprobante.receptor_domicilio == request.domicilio
    assert comprobante.fecha_emision == FECHA_FISCAL_PRUEBA
    assert comprobante.cae == CAE_SINTETICO
    assert comprobante.total == Decimal("1000")


@pytest.mark.asyncio
@pytest.mark.parametrize("cantidad", [0, 1, 2, 3])
async def test_asociacion_implicita_preserva_snapshot_y_clientes(
    db_session, escenario_cliente, cantidad
):
    """Crea o reutiliza sólo si la identidad administrativa es inequívoca."""
    service, request, punto = escenario_cliente
    clientes = await _agregar_clientes(db_session, request.empresa_id, cantidad)
    payload_original = deepcopy(request.model_dump(mode="json"))

    comprobante = await _guardar_sintetico(service, request, punto, commit=True)

    assert request.model_dump(mode="json") == payload_original
    _comprobar_snapshot(comprobante, request)
    guardados = list(
        await db_session.scalars(
            select(Cliente).where(Cliente.empresa_id == request.empresa_id)
        )
    )
    assert len(guardados) == max(1, cantidad)
    if cantidad == 0:
        assert comprobante.cliente_id == guardados[0].id
        assert guardados[0].razon_social == request.razon_social
    elif cantidad == 1:
        assert comprobante.cliente_id == clientes[0].id
    else:
        assert comprobante.cliente_id is None
    for cliente in clientes:
        assert cliente.razon_social.startswith("Registro administrativo sintético")
        assert cliente.condicion_iva == "Monotributo"
        assert cliente.domicilio == "Otro domicilio sintético"
    item = await db_session.scalar(
        select(ComprobanteItem).where(ComprobanteItem.comprobante_id == comprobante.id)
    )
    assert item.codigo == request.items[0].codigo
    assert item.cantidad == request.items[0].cantidad
    assert item.precio_unitario == request.items[0].precio_unitario


@pytest.mark.asyncio
@pytest.mark.parametrize("cantidad_local", [0, 1])
async def test_asociacion_ignora_otro_emisor_y_otro_tipo_documento(
    db_session, escenario_cliente, cantidad_local
):
    """Coincidencias ajenas no convierten una asociación local en ambigua."""
    service, request, punto = escenario_cliente
    otra_empresa = Empresa(
        razon_social="Otro emisor sintético",
        cuit="20000000002",
        condicion_iva="RI",
        domicilio="Domicilio sintético",
        localidad="Localidad sintética",
        provincia="Provincia sintética",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(otra_empresa)
    await db_session.commit()
    ajenos = await _agregar_clientes(db_session, otra_empresa.id, 2)
    otros_tipos = await _agregar_clientes(
        db_session, request.empresa_id, 2, tipo_documento="Pasaporte"
    )
    locales = await _agregar_clientes(db_session, request.empresa_id, cantidad_local)

    comprobante = await _guardar_sintetico(service, request, punto, commit=True)

    assert comprobante.cliente_id is not None
    assert comprobante.cliente_id not in {
        cliente.id for cliente in ajenos + otros_tipos
    }
    if locales:
        assert comprobante.cliente_id == locales[0].id
    asociado = await db_session.get(Cliente, comprobante.cliente_id)
    assert asociado.empresa_id == request.empresa_id
    assert asociado.tipo_documento == "DNI"
    _comprobar_snapshot(comprobante, request)


@pytest.mark.asyncio
@pytest.mark.parametrize("guardar_cliente", [False, True])
@pytest.mark.parametrize("desactivar_cliente", [False, True])
async def test_asociacion_explicita_prevalece_entre_duplicados(
    db_session, escenario_cliente, monkeypatch, guardar_cliente, desactivar_cliente
):
    """El cliente validado se conserva sin una nueva lectura administrativa."""
    service, request, punto = escenario_cliente
    clientes = await _agregar_clientes(db_session, request.empresa_id, 2)
    request = request.model_copy(
        update={"cliente_id": clientes[1].id, "guardar_cliente": guardar_cliente}
    )
    await service._validar_datos(request)
    if desactivar_cliente:
        clientes[1].activo = False
        await db_session.commit()

    async def prohibir_nueva_lectura(*args, **kwargs):
        pytest.fail("El ID explícito no necesita otra consulta después de CAE")

    monkeypatch.setattr(db_session, "execute", prohibir_nueva_lectura)

    comprobante = await _guardar_sintetico(service, request, punto, commit=True)

    assert comprobante.cliente_id == clientes[1].id
    _comprobar_snapshot(comprobante, request)


@pytest.mark.asyncio
async def test_asociacion_explicita_rechaza_cliente_de_otro_emisor(
    db_session, escenario_cliente
):
    """La validación vigente bloquea la referencia ajena antes de solicitar CAE."""
    service, request, punto = escenario_cliente
    otra_empresa = Empresa(
        razon_social="Emisor ajeno sintético",
        cuit="20000000002",
        condicion_iva="RI",
        domicilio="Domicilio sintético",
        localidad="Localidad sintética",
        provincia="Provincia sintética",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(otra_empresa)
    await db_session.commit()
    [ajeno] = await _agregar_clientes(db_session, otra_empresa.id, 1)
    request = request.model_copy(update={"cliente_id": ajeno.id})

    with pytest.raises(ValidationError, match="empresa activa"):
        await service._validar_datos(request)

    await db_session.rollback()
    assert list(await db_session.scalars(select(Comprobante))) == []


@pytest.mark.asyncio
async def test_cliente_id_cero_no_cambia_payload_y_se_rechaza_pre_cae(
    db_session, escenario_cliente
):
    """La referencia cero conserva la validación pre-CAE y el snapshot vigente."""
    service, request, _punto = escenario_cliente
    request = request.model_copy(update={"cliente_id": 0})
    normalizado = service.normalizar_receptor(request)
    assert normalizado.cliente_id == 0
    assert normalizado.model_dump(mode="json") == request.model_dump(mode="json")

    with pytest.raises(ValidationError, match="empresa activa"):
        await service._validar_datos(normalizado)

    assert list(await db_session.scalars(select(Comprobante))) == []
    assert list(await db_session.scalars(select(IntentoEmisionFiscal))) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("guardar_cliente", [False, True])
async def test_guardado_cliente_id_cero_conserva_compatibilidad_historica(
    db_session, escenario_cliente, guardar_cliente
):
    """La persistencia no redefine una referencia legacy que el preflight rechaza."""
    service, request, punto = escenario_cliente
    request = request.model_copy(
        update={"cliente_id": 0, "guardar_cliente": guardar_cliente}
    )
    if guardar_cliente:
        comprobante = await _guardar_sintetico(service, request, punto, commit=True)
        assert comprobante.cliente_id > 0
        assert request.cliente_id == 0
        _comprobar_snapshot(comprobante, request)
    else:
        with pytest.raises(IntegrityError):
            await _guardar_sintetico(service, request, punto)
        await db_session.rollback()
        assert list(await db_session.scalars(select(Comprobante))) == []


@pytest.mark.asyncio
async def test_sin_alta_automatica_no_asocia_duplicados(db_session, escenario_cliente):
    """Sin selección explícita ni alta solicitada se conserva cliente_id nulo."""
    service, request, punto = escenario_cliente
    await _agregar_clientes(db_session, request.empresa_id, 2)
    request = request.model_copy(update={"guardar_cliente": False})

    comprobante = await _guardar_sintetico(service, request, punto, commit=True)

    assert comprobante.cliente_id is None
    assert len(list(await db_session.scalars(select(Cliente)))) == 2
    _comprobar_snapshot(comprobante, request)


@pytest.mark.asyncio
async def test_duplicado_administrativo_aparece_despues_del_preflight(
    db_session, escenario_cliente
):
    """Un alta administrativa posterior a validar no impide guardar el CAE."""
    service, request, punto = escenario_cliente
    await _agregar_clientes(db_session, request.empresa_id, 1)
    await service._validar_datos(request)
    await _agregar_clientes(db_session, request.empresa_id, 1)

    comprobante = await _guardar_sintetico(service, request, punto, commit=True)

    assert comprobante.cliente_id is None
    _comprobar_snapshot(comprobante, request)


@pytest.mark.asyncio
async def test_cliente_explicito_eliminado_conserva_fallo_fk_y_rollback(
    db_session, escenario_cliente
):
    """La corrección no oculta el fallo de FK vigente si se borra el cliente elegido."""
    service, request, punto = escenario_cliente
    [cliente] = await _agregar_clientes(db_session, request.empresa_id, 1)
    request = request.model_copy(update={"cliente_id": cliente.id})
    await service._validar_datos(request)
    await db_session.delete(cliente)
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await _guardar_sintetico(service, request, punto)

    await db_session.rollback()
    assert list(await db_session.scalars(select(Comprobante))) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("cantidad", [0, 2])
async def test_guardado_diferido_conserva_atomicidad_y_rollback(
    db_session, escenario_cliente, monkeypatch, cantidad
):
    """Comprobante, ítems y alta administrativa respetan la transacción del caller."""
    service, request, punto = escenario_cliente
    await _agregar_clientes(db_session, request.empresa_id, cantidad)

    async def prohibir_commit():
        pytest.fail(
            "El guardado compartido no puede confirmar la transacción del caller"
        )

    monkeypatch.setattr(db_session, "commit", prohibir_commit)
    comprobante = await _guardar_sintetico(service, request, punto)
    await db_session.flush()
    comprobante_id = comprobante.id
    assert await db_session.get(Comprobante, comprobante_id) is not None
    assert list(await db_session.scalars(select(ComprobanteItem)))

    await db_session.rollback()

    assert await db_session.get(Comprobante, comprobante_id) is None
    assert list(await db_session.scalars(select(ComprobanteItem))) == []
    assert len(list(await db_session.scalars(select(Cliente)))) == cantidad


@pytest.mark.asyncio
@pytest.mark.parametrize("tipo_error", [SQLAlchemyTimeoutError, OperationalError])
async def test_error_db_de_asociacion_propaga_y_permite_rollback(
    db_session, escenario_cliente, monkeypatch, tipo_error
):
    """Un error de base no se transforma en una asociación nula exitosa."""
    service, request, punto = escenario_cliente
    error = (
        SQLAlchemyTimeoutError()
        if tipo_error is SQLAlchemyTimeoutError
        else OperationalError("SELECT sintético", {}, RuntimeError("fallo sintético"))
    )

    async def fallar_consulta(*args, **kwargs):
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "execute", fallar_consulta)
        with pytest.raises(tipo_error) as captura:
            await _guardar_sintetico(service, request, punto)
        assert captura.value is error
    await db_session.rollback()
    assert list(await db_session.scalars(select(Comprobante))) == []
    assert list(await db_session.scalars(select(Cliente))) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["individual", "batch"])
@pytest.mark.parametrize("fallar_db", [False, True])
async def test_autorizacion_sintetica_con_duplicados_y_error_post_cae(
    db_session, escenario_cliente, test_empresa, monkeypatch, modo, fallar_db
):
    """La ambigüedad permite guardar; un fallo DB conserva incertidumbre y reserva."""
    service, request, punto = escenario_cliente
    await _agregar_clientes(db_session, request.empresa_id, 2)
    db_session.add(
        Certificado(
            empresa_id=request.empresa_id,
            nombre="Certificado sintético",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2027, 1, 1),
            archivo_crt="sintetico.crt",
            archivo_key="sintetico.key",
            activo=True,
            ambiente=settings.arca_env,
        )
    )
    await db_session.commit()
    operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto,
        requests=[request],
        batch=modo == "batch",
    )
    llamadas_cae = 0

    class WsfeSintetico:
        def __init__(self, *args, **kwargs):
            pass

        async def fe_comp_ultimo_autorizado(self, *args, **kwargs):
            return 0

        async def fe_cae_solicitar(self, arca_request):
            nonlocal llamadas_cae
            llamadas_cae += 1
            return CAEResponse(
                cae=CAE_SINTETICO,
                cae_vencimiento=VENCIMIENTO_CAE_SINTETICO,
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

        async def fe_cae_solicitar_lote(self, arca_requests):
            return [await self.fe_cae_solicitar(arca_requests[0])]

    async def ticket_sintetico(self, *args, **kwargs):
        return SimpleNamespace(token="token-sintetico", sign="firma-sintetica")

    async def punto_sintetico(self, *args, **kwargs):
        return None

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", WsfeSintetico)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", ticket_sintetico)
    monkeypatch.setattr(
        FacturacionService, "_validar_punto_venta_habilitado", punto_sintetico
    )
    ejecutar = db_session.execute

    async def fallar_asociacion_post_cae(statement, *args, **kwargs):
        if llamadas_cae and any(
            columna.get("entity") is Cliente
            for columna in getattr(statement, "column_descriptions", [])
        ):
            raise SQLAlchemyTimeoutError()
        return await ejecutar(statement, *args, **kwargs)

    if fallar_db:
        monkeypatch.setattr(db_session, "execute", fallar_asociacion_post_cae)
    if modo == "individual":
        resultado = await service.emitir_comprobante(
            request,
            operacion_id=operacion.id,
            contexto_rece=contexto,
            contextos_operacion=[contexto],
        )
    else:
        [resultado] = await service.emitir_comprobantes_lote(
            [request], max_registros=1, contextos=metadata
        )
    monkeypatch.setattr(db_session, "execute", ejecutar)

    assert llamadas_cae == 1
    intento = await db_session.scalar(select(IntentoEmisionFiscal))
    assert intento.numero_planificado == 1
    if fallar_db:
        assert resultado.exito is False
        assert resultado.requiere_reconciliacion is True
        assert intento.estado == "requiere_reconciliacion"
        assert list(await db_session.scalars(select(Comprobante))) == []
    else:
        assert resultado.exito is True
        comprobante = await db_session.get(Comprobante, resultado.comprobante_id)
        assert comprobante.cliente_id is None
        _comprobar_snapshot(comprobante, request)
        assert intento.estado == "autorizado"
        replay = await service._respuesta_desde_intento_resuelto(intento)
        assert replay.model_dump(mode="json") == resultado.model_dump(mode="json")
        assert llamadas_cae == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("origen", ["stale", "externo"])
async def test_recuperacion_autorizada_y_externa_preservan_snapshot_ambiguo(
    db_session, escenario_cliente, test_empresa, origen
):
    """Los otros dos consumidores guardan la evidencia sin elegir un duplicado."""
    service, request, punto = escenario_cliente
    await _agregar_clientes(db_session, request.empresa_id, 2)
    if origen == "externo":
        comprobante = await LoteComprobantesService(
            db_session
        )._crear_o_vincular_comprobante_externo(
            empresa=test_empresa,
            request=request,
            punto_venta_numero=punto.numero,
            numero=1,
            cae=CAE_SINTETICO,
            cae_vencimiento=VENCIMIENTO_CAE_SINTETICO,
        )
        assert comprobante.origen_emision == "arca_web"
    else:
        lote = LoteComprobante(
            empresa_id=request.empresa_id,
            nombre_archivo="sintetico.xlsx",
            archivo_hash="0" * 64,
            estado="requiere_reconciliacion",
        )
        db_session.add(lote)
        await db_session.flush()
        grupo = LoteComprobanteGrupo(
            empresa_id=request.empresa_id,
            lote_id=lote.id,
            comprobante_ref="SINTETICO",
            estado="requiere_reconciliacion",
            payload_json=request.model_dump(mode="json"),
            total_estimado=Decimal("1000"),
        )
        db_session.add(grupo)
        await db_session.flush()
        payload_original = deepcopy(grupo.payload_json)
        comprobante = await service._crear_o_vincular_intento_autorizado(
            intento=SimpleNamespace(
                id=1,
                empresa_id=request.empresa_id,
                punto_venta_id=punto.id,
                tipo_comprobante=request.tipo_comprobante,
                numero_planificado=1,
                fecha_emision=request.fecha_emision,
                total=Decimal("1000"),
                grupo_id=grupo.id,
            ),
            consulta_arca=SimpleNamespace(
                cae=CAE_SINTETICO,
                cae_vencimiento=VENCIMIENTO_CAE_SINTETICO,
            ),
        )
        assert grupo.estado == "autorizado"
        assert grupo.comprobante_id == comprobante.id
        assert grupo.payload_json == payload_original
    await db_session.commit()
    await db_session.refresh(comprobante)
    assert comprobante.cliente_id is None
    _comprobar_snapshot(comprobante, request)
