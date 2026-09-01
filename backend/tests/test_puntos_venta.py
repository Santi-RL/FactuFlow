"""Aceptación end-to-end de PF-19D para autoridad y uso de puntos."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.elegibilidad_rece import PuntoVentaElegibilidadReceRevision
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceActual,
    PuntoVentaGuardaEmisionRece,
)
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.services.elegibilidad_rece_service import ElegibilidadReceService
from app.services.puntos_venta_arca_service import PuntosVentaArcaService
from app.services.constancia_puntos_venta_service import (
    DatosConstanciaPuntosVenta,
    PuntoVentaConstancia,
)


def _headers_admin(
    admin_auth_headers: dict[str, str],
    empresa: Empresa,
) -> dict[str, str]:
    return {**admin_auth_headers, "X-Empresa-Id": str(empresa.id)}


class _ClienteWsfe:
    def __init__(self, puntos: list[SimpleNamespace]) -> None:
        self.puntos = puntos

    async def fe_param_get_ptos_venta(self) -> list[SimpleNamespace]:
        return self.puntos


async def _configurar_wsfe(
    monkeypatch: pytest.MonkeyPatch,
    puntos: list[SimpleNamespace],
) -> None:
    from app.api import puntos_venta as puntos_venta_api

    cliente = _ClienteWsfe(puntos)

    async def fake_get_wsfe_client(*_args: Any, **_kwargs: Any) -> _ClienteWsfe:
        return cliente

    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", fake_get_wsfe_client)


def _remoto(
    numero: int,
    *,
    tipo: str | None = "CAE - RECE",
    bloqueado: str = "N",
    fecha_baja: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        numero=numero,
        emision_tipo=tipo,
        bloqueado=bloqueado,
        fecha_baja=fecha_baja,
    )


@pytest.fixture
async def segundo_emisor(db_session: AsyncSession) -> Empresa:
    emisor = Empresa(
        razon_social="Segundo emisor PF-19D",
        cuit="30123456789",
        condicion_iva="Exento",
        domicilio="Calle Segunda 2",
        localidad="CABA",
        provincia="CABA",
        codigo_postal="1000",
        inicio_actividades=datetime(2020, 1, 1).date(),
    )
    db_session.add(emisor)
    await db_session.commit()
    await db_session.refresh(emisor)
    return emisor


async def _crear_guarda_activa(
    db_session: AsyncSession,
    *,
    punto: PuntoVenta,
    usuario: Usuario,
) -> None:
    head = await db_session.scalar(
        select(PuntoVentaElegibilidadReceActual).where(
            PuntoVentaElegibilidadReceActual.punto_venta_id == punto.id,
            PuntoVentaElegibilidadReceActual.ambiente == "produccion",
        )
    )
    assert head is not None
    service = ElegibilidadReceService(db_session)
    contexto = await service.exigir_contexto_actual(
        empresa_id=int(punto.empresa_id),
        punto_venta_id=int(punto.id),
        ambiente="produccion",
    )
    operacion = OperacionIdempotente(
        empresa_id=int(punto.empresa_id),
        usuario_id=int(usuario.id),
        idempotency_key="pf19d-guarda-activa",
        tipo_operacion="emitir_comprobante",
        payload_hash="a" * 64,
        rece_snapshot_hash=service.calcular_digest_contextos([contexto]),
        estado="en_proceso",
    )
    db_session.add(operacion)
    await db_session.flush()
    db_session.add(
        OperacionIdempotenteElegibilidadRece(
            operacion_id=int(operacion.id),
            empresa_id=int(punto.empresa_id),
            punto_venta_id=int(punto.id),
            ambiente="produccion",
            elegibilidad_revision_id=int(head.revision_actual_id),
            punto_venta_revision_fiscal=int(punto.revision_fiscal),
        )
    )
    await db_session.flush()
    db_session.add(
        PuntoVentaGuardaEmisionRece(
            token="f" * 64,
            fase="pre_arca",
            operacion_id=int(operacion.id),
            empresa_id=int(punto.empresa_id),
            punto_venta_id=int(punto.id),
            ambiente="produccion",
            elegibilidad_revision_id=int(head.revision_actual_id),
            punto_venta_revision_fiscal=int(punto.revision_fiscal),
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_sync_wsfe_descubre_clasifica_y_acredita_sin_constancia(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una comprobación manual crea un snapshot completo y seleccionable."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(
        monkeypatch,
        [
            _remoto(1),
            _remoto(2, tipo="Comprobantes en línea"),
            _remoto(3, bloqueado="S"),
            _remoto(4, fecha_baja="20260830"),
        ],
    )

    response = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["total_arca"] == 4
    listado = await client.get("/api/puntos-venta", headers=auth_headers)
    assert listado.status_code == 200, listado.text
    por_numero = {item["numero"]: item for item in listado.json()}
    assert por_numero[1]["usar_en_factuflow"] is True
    assert por_numero[1]["seleccionable_para_emision"] is True
    assert por_numero[1]["elegibilidad_rece"]["fuente"] == "sincronizacion_wsfe"
    assert por_numero[2]["es_webservice"] is False
    assert por_numero[2]["usar_en_factuflow"] is False
    assert por_numero[2]["elegibilidad_rece"]["estado"] == "no_rece"
    assert por_numero[3]["usar_en_factuflow"] is True
    assert por_numero[3]["seleccionable_para_emision"] is False
    assert por_numero[4]["usar_en_factuflow"] is True
    assert por_numero[4]["seleccionable_para_emision"] is False

    revisiones = list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceRevision).where(
                    PuntoVentaElegibilidadReceRevision.evidencia_tipo
                    == "wsfe_param_get_ptos_venta_v1"
                )
            )
        ).scalars()
    )
    assert {revision.punto_venta_numero_snapshot for revision in revisiones} == {
        1,
        3,
        4,
    }
    assert all(revision.evidencia_sha256 is None for revision in revisiones)


@pytest.mark.asyncio
async def test_sync_wsfe_acredita_el_ambiente_configurado(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La autoridad WSFE no mezcla homologación con producción."""
    monkeypatch.setattr(settings, "arca_env", "homologacion")
    await _configurar_wsfe(monkeypatch, [_remoto(5)])

    response = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    punto = await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 5))
    assert punto is not None
    visible = await ElegibilidadReceService(db_session).obtener_estado_visible(
        punto,
        ambiente="homologacion",
    )
    assert visible.estado == "verificado_rece"
    assert visible.fuente == "sincronizacion_wsfe"
    assert (await client.get("/api/puntos-venta", headers=auth_headers)).json()[0][
        "seleccionable_para_emision"
    ] is True


@pytest.mark.asyncio
async def test_cambio_tecnico_no_reutiliza_autoridad_de_otro_ambiente(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un snapshot productivo no mantiene vigente la cabeza de homologación."""
    monkeypatch.setattr(settings, "arca_env", "homologacion")
    await _configurar_wsfe(monkeypatch, [_remoto(6)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    punto = await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 6))
    assert punto is not None

    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(6, bloqueado="S")])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200

    servicio = ElegibilidadReceService(db_session)
    homologacion = await servicio.obtener_estado_visible(
        punto,
        ambiente="homologacion",
    )
    produccion = await servicio.obtener_estado_visible(
        punto,
        ambiente="produccion",
    )
    assert homologacion.estado == "no_verificado"
    assert produccion.estado == "verificado_rece"


@pytest.mark.asyncio
async def test_preferencia_compartida_persiste_en_sync_y_desbloqueo(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ARCA no revierte una deshabilitación explícita del emisor."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(10)])
    primera = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )
    assert primera.status_code == 200, primera.text
    punto = (
        await db_session.execute(select(PuntoVenta).where(PuntoVenta.numero == 10))
    ).scalar_one()
    revision_inicial = int(punto.revision_fiscal)

    deshabilitar = await client.put(
        f"/api/puntos-venta/{punto.id}",
        headers=auth_headers,
        json={"usar_en_factuflow": False},
    )
    assert deshabilitar.status_code == 200, deshabilitar.text
    assert deshabilitar.json()["usar_en_factuflow"] is False
    assert deshabilitar.json()["revision_fiscal"] == revision_inicial + 1
    assert deshabilitar.json()["elegibilidad_rece"]["estado"] == "verificado_rece"

    await _configurar_wsfe(monkeypatch, [_remoto(10, bloqueado="S")])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    await _configurar_wsfe(monkeypatch, [_remoto(19)])
    ausencia = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )
    assert ausencia.status_code == 200, ausencia.text
    assert ausencia.json()["desactivados_ausentes"] == 1
    await _configurar_wsfe(monkeypatch, [_remoto(10), _remoto(19)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    await _configurar_wsfe(monkeypatch, [_remoto(10)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    listado = await client.get("/api/puntos-venta", headers=auth_headers)
    dto = listado.json()[0]
    assert dto["bloqueado"] is False
    assert dto["usar_en_factuflow"] is False
    assert dto["seleccionable_para_emision"] is False


@pytest.mark.asyncio
async def test_preferencia_no_cambia_con_guarda_activa(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_user: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una operación pre-ARCA inmoviliza la preferencia y su revisión."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(11)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    punto = await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 11))
    assert punto is not None
    revision = int(punto.revision_fiscal)
    await _crear_guarda_activa(db_session, punto=punto, usuario=test_user)

    response = await client.put(
        f"/api/puntos-venta/{punto.id}",
        headers=auth_headers,
        json={"usar_en_factuflow": False},
    )

    assert response.status_code == 409, response.text
    assert "solicitud fiscal activa" in response.json()["detail"]
    await db_session.refresh(punto)
    assert punto.usar_en_factuflow is True
    assert punto.revision_fiscal == revision


@pytest.mark.asyncio
async def test_sync_con_guarda_activa_revierte_el_snapshot_completo(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_user: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una carrera pre-ARCA no deja cambios parciales ni puntos nuevos."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(70), _remoto(71)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    puntos = {
        punto.numero: punto
        for punto in (
            await db_session.execute(
                select(PuntoVenta).where(PuntoVenta.numero.in_([70, 71]))
            )
        ).scalars()
    }
    revisiones = {
        numero: int(punto.revision_fiscal) for numero, punto in puntos.items()
    }
    await _crear_guarda_activa(db_session, punto=puntos[71], usuario=test_user)

    await _configurar_wsfe(
        monkeypatch,
        [_remoto(70, bloqueado="S"), _remoto(72)],
    )
    response = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )

    assert response.status_code == 409, response.text
    assert "solicitud fiscal activa" in response.json()["detail"]
    for numero, punto in puntos.items():
        await db_session.refresh(punto)
        assert punto.activo is True
        assert punto.bloqueado is False
        assert punto.revision_fiscal == revisiones[numero]
    assert (
        await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 72))
        is None
    )


@pytest.mark.asyncio
async def test_sync_y_listado_aislan_emisores(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    test_empresa: Empresa,
    segundo_emisor: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La autoridad WSFE y la preferencia quedan dentro del emisor activo."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(12)])
    assert (
        await client.post(
            "/api/puntos-venta/sincronizar-arca",
            headers=_headers_admin(admin_auth_headers, test_empresa),
        )
    ).status_code == 200
    await _configurar_wsfe(monkeypatch, [_remoto(13)])
    assert (
        await client.post(
            "/api/puntos-venta/sincronizar-arca",
            headers=_headers_admin(admin_auth_headers, segundo_emisor),
        )
    ).status_code == 200

    primero = await client.get(
        "/api/puntos-venta",
        headers=_headers_admin(admin_auth_headers, test_empresa),
    )
    segundo = await client.get(
        "/api/puntos-venta",
        headers=_headers_admin(admin_auth_headers, segundo_emisor),
    )
    assert [item["numero"] for item in primero.json()] == [12]
    assert [item["numero"] for item in segundo.json()] == [13]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "puntos",
    [
        [],
        [_remoto(20), _remoto(20)],
        [SimpleNamespace(numero=20, bloqueado="N", fecha_baja=None)],
        [_remoto(20, tipo=None)],
    ],
)
async def test_sync_invalida_no_modifica_estado(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
    puntos: list[SimpleNamespace],
) -> None:
    """Vacíos, duplicados y tipos ausentes fallan antes de cualquier escritura."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    previo = PuntoVenta(
        numero=99,
        nombre="Conservar",
        empresa_id=test_empresa.id,
        usar_en_factuflow=True,
    )
    db_session.add(previo)
    await ElegibilidadReceService(db_session).crear_contextos_iniciales_no_verificados(
        previo
    )
    await db_session.commit()
    await _configurar_wsfe(monkeypatch, puntos)

    response = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )

    assert response.status_code == 503, response.text
    await db_session.refresh(previo)
    assert previo.activo is True
    assert previo.revision_fiscal == 1
    assert (
        await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 20))
        is None
    )
    assert (
        list((await db_session.execute(select(OperacionIdempotente))).scalars()) == []
    )
    assert (
        list((await db_session.execute(select(IntentoEmisionFiscal))).scalars()) == []
    )
    assert (
        list((await db_session.execute(select(PuntoVentaGuardaEmisionRece))).scalars())
        == []
    )


@pytest.mark.asyncio
async def test_timeout_wsfe_no_modifica_estado_ni_crea_estado_fiscal(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un timeout de lectura queda antes de operaciones, intentos y reservas."""
    from app.api import puntos_venta as puntos_venta_api

    monkeypatch.setattr(settings, "arca_env", "produccion")
    previo = PuntoVenta(numero=98, empresa_id=test_empresa.id, usar_en_factuflow=True)
    db_session.add(previo)
    await ElegibilidadReceService(db_session).crear_contextos_iniciales_no_verificados(
        previo
    )
    await db_session.commit()

    class ClienteConTimeout:
        async def fe_param_get_ptos_venta(self) -> list[SimpleNamespace]:
            raise TimeoutError("timeout sintético")

    async def cliente_timeout(*_args: Any, **_kwargs: Any) -> ClienteConTimeout:
        return ClienteConTimeout()

    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", cliente_timeout)
    response = await client.post(
        "/api/puntos-venta/sincronizar-arca", headers=auth_headers
    )

    assert response.status_code == 503, response.text
    await db_session.refresh(previo)
    assert previo.activo is True
    assert previo.revision_fiscal == 1
    assert (
        list((await db_session.execute(select(OperacionIdempotente))).scalars()) == []
    )
    assert (
        list((await db_session.execute(select(IntentoEmisionFiscal))).scalars()) == []
    )
    assert (
        list((await db_session.execute(select(PuntoVentaGuardaEmisionRece))).scalars())
        == []
    )


@pytest.mark.asyncio
async def test_usuario_edita_descriptivos_y_no_campos_tecnicos(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cualquier usuario del emisor edita descripciones, nunca señales ARCA."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(30)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    punto = await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 30))
    assert punto is not None
    revision = int(punto.revision_fiscal)

    descriptivo = await client.put(
        f"/api/puntos-venta/{punto.id}",
        headers=auth_headers,
        json={"domicilio": "Av. Manual 123", "nombre_fantasia": "Sucursal"},
    )
    assert descriptivo.status_code == 200, descriptivo.text
    assert descriptivo.json()["domicilio_fuente"] == "manual"
    assert descriptivo.json()["nombre_fantasia_fuente"] == "manual"
    assert descriptivo.json()["revision_fiscal"] == revision

    tecnico = await client.put(
        f"/api/puntos-venta/{punto.id}",
        headers=auth_headers,
        json={"bloqueado": True},
    )
    assert tecnico.status_code == 409, tecnico.text
    assert "los informa ARCA" in tecnico.json()["detail"]

    await _configurar_wsfe(monkeypatch, [_remoto(30), _remoto(33, tipo="Otro")])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    otro = await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 33))
    assert otro is not None
    habilitar_otro = await client.put(
        f"/api/puntos-venta/{otro.id}",
        headers=auth_headers,
        json={"usar_en_factuflow": True},
    )
    assert habilitar_otro.status_code == 409, habilitar_otro.text
    assert (
        "no informa este punto como compatible con CAE"
        in habilitar_otro.json()["detail"]
    )


@pytest.mark.asyncio
async def test_constancia_es_opcional_descriptiva_y_no_consulta_wsfe(
    client: AsyncClient,
    auth_headers: dict[str, str],
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El PDF sobrescribe descripciones sin cambiar autoridad ni revisión."""
    from app.api import puntos_venta as puntos_venta_api

    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(31)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    punto = await db_session.scalar(select(PuntoVenta).where(PuntoVenta.numero == 31))
    assert punto is not None
    manual = await client.put(
        f"/api/puntos-venta/{punto.id}",
        headers=auth_headers,
        json={
            "domicilio": "Av. Manual 123",
            "nombre_fantasia": "Sucursal manual",
        },
    )
    assert manual.status_code == 200, manual.text
    assert manual.json()["domicilio_fuente"] == "manual"
    assert manual.json()["nombre_fantasia_fuente"] == "manual"
    revision_antes = int(punto.revision_fiscal)
    head_antes = (
        await ElegibilidadReceService(db_session).obtener_estado_visible(
            punto,
            ambiente="produccion",
        )
    ).revision_id

    datos = DatosConstanciaPuntosVenta(
        cuit=test_empresa.cuit,
        puntos_venta=[
            PuntoVentaConstancia(
                numero=31,
                sistema="RECE para aplicativo y web services",
                domicilio="Av. ARCA 456",
                nombre_fantasia="Sucursal ARCA",
                es_webservice=True,
            ),
            PuntoVentaConstancia(
                numero=32,
                sistema="Comprobantes en línea",
                domicilio="Calle Informativa 1",
                es_webservice=False,
            ),
        ],
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "extraer_texto_constancia_puntos_pdf",
        lambda _contenido: "constancia sintética",
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "parsear_constancia_puntos_venta",
        lambda _texto: datos,
    )

    async def prohibido(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("La constancia descriptiva no debe consultar WSFE")

    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", prohibido)
    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin(admin_auth_headers, test_empresa),
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["creados"] == 1
    assert response.json()["actualizados"] == 1
    await db_session.refresh(punto)
    assert punto.domicilio == "Av. ARCA 456"
    assert punto.domicilio_fuente == "constancia_arca"
    assert punto.nombre_fantasia_fuente == "constancia_arca"
    assert punto.revision_fiscal == revision_antes
    assert (
        await ElegibilidadReceService(db_session).obtener_estado_visible(
            punto,
            ambiente="produccion",
        )
    ).revision_id == head_antes
    informativo = await db_session.scalar(
        select(PuntoVenta).where(PuntoVenta.numero == 32)
    )
    assert informativo is not None
    assert informativo.es_webservice is False
    assert informativo.activo is False
    assert informativo.usar_en_factuflow is False


@pytest.mark.asyncio
async def test_punto_manual_no_se_puede_crear(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    test_empresa: Empresa,
) -> None:
    """El contrato legacy permanece, pero el servidor protege la autoridad."""
    response = await client.post(
        "/api/puntos-venta",
        headers=_headers_admin(admin_auth_headers, test_empresa),
        json={"numero": 40, "nombre": "Manual"},
    )
    assert response.status_code == 409, response.text
    assert "Comprobar con ARCA" in response.json()["detail"]


@pytest.mark.parametrize(("antiguedad_dias", "esperada"), [(89, False), (90, True)])
@pytest.mark.asyncio
async def test_frescura_wsfe_sigue_siendo_de_90_dias(
    db_session: AsyncSession,
    test_empresa: Empresa,
    antiguedad_dias: int,
    esperada: bool,
) -> None:
    """PF-19D conserva la política temporal existente."""
    ahora = datetime(2026, 8, 31, 12, 0, 0)
    servicio = ElegibilidadReceService(db_session, ahora=ahora)
    punto = PuntoVenta(
        numero=50,
        empresa_id=test_empresa.id,
        ultima_comprobacion_arca_en=ahora - timedelta(days=antiguedad_dias),
    )
    assert servicio.comprobacion_arca_desactualizada(punto) is esperada


@pytest.mark.asyncio
async def test_preflight_agrupa_varios_puntos_en_un_solo_snapshot(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_user: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Varios puntos vencidos disparan una sola comprobación por emisor."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    await _configurar_wsfe(monkeypatch, [_remoto(51), _remoto(52)])
    assert (
        await client.post("/api/puntos-venta/sincronizar-arca", headers=auth_headers)
    ).status_code == 200
    puntos = list(
        (
            await db_session.execute(
                select(PuntoVenta).where(PuntoVenta.numero.in_([51, 52]))
            )
        ).scalars()
    )
    ahora = datetime(2026, 8, 31, 12, 0, 0)
    for punto in puntos:
        punto.ultima_comprobacion_arca_en = ahora - timedelta(days=89)
    await db_session.commit()
    comprobaciones: list[dict[str, object]] = []

    async def contar_comprobacion(
        self: PuntosVentaArcaService,
        **kwargs: object,
    ) -> dict[str, int | datetime]:
        comprobaciones.append(kwargs)
        return {
            "total_arca": 2,
            "nuevos": 0,
            "existentes": 2,
            "actualizados": 0,
            "desactivados_ausentes": 0,
            "comprobado_en": ahora,
        }

    monkeypatch.setattr(PuntosVentaArcaService, "sincronizar", contar_comprobacion)
    preflight = PuntosVentaArcaService(db_session, ahora=ahora)
    ids = {int(punto.id) for punto in puntos}
    assert (
        await preflight.asegurar_comprobacion_reciente(
            empresa_id=int(test_empresa.id),
            puntos_venta_ids=ids,
            actor_usuario_id=int(test_user.id),
        )
        is False
    )
    assert comprobaciones == []

    for punto in puntos:
        punto.ultima_comprobacion_arca_en = ahora - timedelta(days=90)
    await db_session.commit()
    assert (
        await preflight.asegurar_comprobacion_reciente(
            empresa_id=int(test_empresa.id),
            puntos_venta_ids=ids,
            actor_usuario_id=int(test_user.id),
        )
        is True
    )
    assert len(comprobaciones) == 1


@pytest.mark.asyncio
async def test_numero_sigue_siendo_unico_por_emisor(
    db_session: AsyncSession,
    test_empresa: Empresa,
) -> None:
    """La autoridad remota no relaja la restricción estructural local."""
    db_session.add_all(
        [
            PuntoVenta(numero=60, empresa_id=test_empresa.id),
            PuntoVenta(numero=60, empresa_id=test_empresa.id),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
