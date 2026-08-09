"""Tests de puntos de venta y autoridad RECE."""

import hashlib
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.services.constancia_puntos_venta_service import (
    DatosConstanciaPuntosVenta,
    PuntoVentaConstancia,
)
from app.services.elegibilidad_rece_service import (
    AtestacionPuntoRece,
    ContextoElegibilidadRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)


HOY_RECE_PRUEBA = date(2026, 8, 9)
SENAL_RECE_EXACTA = "RECE para aplicativo y web services"
EVIDENCIA_PRIVADA_RECE = {
    "evidencia_sha256",
    "clasificador_version",
    "empresa_cuit_snapshot",
    "punto_venta_numero_snapshot",
    "actor_usuario_id_snapshot",
    "creado_por_usuario_id",
}
CLAVES_PUBLICAS_ELEGIBILIDAD_RECE = {
    "ambiente",
    "estado",
    "estado_efectivo",
    "fuente",
    "revision_id",
    "revision",
    "punto_revision_fiscal",
    "verificado_en",
    "vigente_hasta",
    "motivo",
}


def _headers_admin_emisor(
    admin_auth_headers: dict[str, str],
    empresa: Empresa,
) -> dict[str, str]:
    """Agregar el emisor activo explícito a los headers administrativos."""
    return {**admin_auth_headers, "X-Empresa-Id": str(empresa.id)}


def _configurar_reloj_y_ambiente_rece(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ambiente: str,
) -> None:
    """Fijar ambiente y día argentino sin depender del reloj de ejecución."""
    from app.api import puntos_venta as puntos_venta_api
    from app.core.config import settings

    class ElegibilidadReceServiceConReloj(ElegibilidadReceService):
        """Servicio de prueba con día argentino determinista."""

        def __init__(self, db: AsyncSession) -> None:
            super().__init__(db, hoy=HOY_RECE_PRUEBA)

    monkeypatch.setattr(settings, "arca_env", ambiente)
    monkeypatch.setattr(
        puntos_venta_api,
        "ElegibilidadReceService",
        ElegibilidadReceServiceConReloj,
    )


def _configurar_constancia_sintetica(
    monkeypatch: pytest.MonkeyPatch,
    datos: DatosConstanciaPuntosVenta,
    *,
    estado_arca: dict[int, dict[str, str | bool | None]] | None,
) -> None:
    """Doblar PDF, parser y lectura segura ARCA sin conexiones externas."""
    from app.api import puntos_venta as puntos_venta_api

    async def fake_estado_arca(
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[int, dict[str, str | bool | None]] | None:
        return estado_arca

    monkeypatch.setattr(
        puntos_venta_api,
        "extraer_texto_constancia_puntos_pdf",
        lambda _contenido: "texto constancia sintética",
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "parsear_constancia_puntos_venta",
        lambda _texto: datos,
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "_obtener_estado_puntos_arca",
        fake_estado_arca,
    )


async def _revisiones_punto(
    db_session: AsyncSession,
    punto_venta_id: int,
) -> list[PuntoVentaElegibilidadReceRevision]:
    """Listar el ledger de un punto en orden estable por ambiente y revisión."""
    return list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceRevision)
                .where(
                    PuntoVentaElegibilidadReceRevision.punto_venta_id == punto_venta_id
                )
                .order_by(
                    PuntoVentaElegibilidadReceRevision.ambiente,
                    PuntoVentaElegibilidadReceRevision.revision,
                )
            )
        ).scalars()
    )


async def _crear_guarda_rece_activa(
    db_session: AsyncSession,
    *,
    punto: PuntoVenta,
    usuario: Usuario,
    idempotency_key: str,
    token: str,
) -> None:
    """Crear una guarda pre-ARCA coherente para probar mutaciones atómicas."""
    head = (
        await db_session.execute(
            select(PuntoVentaElegibilidadReceActual).where(
                PuntoVentaElegibilidadReceActual.punto_venta_id == punto.id,
                PuntoVentaElegibilidadReceActual.ambiente == "produccion",
            )
        )
    ).scalar_one()
    contexto = ContextoElegibilidadRece(
        empresa_id=int(punto.empresa_id),
        punto_venta_id=int(punto.id),
        punto_venta_numero=int(punto.numero),
        ambiente="produccion",
        elegibilidad_revision_id=int(head.revision_actual_id),
        punto_venta_revision_fiscal=int(punto.revision_fiscal),
    )
    service = ElegibilidadReceService(db_session)
    operacion = OperacionIdempotente(
        empresa_id=contexto.empresa_id,
        usuario_id=int(usuario.id),
        idempotency_key=idempotency_key,
        tipo_operacion="emitir_comprobante",
        payload_hash="7" * 64,
        rece_snapshot_hash=service.calcular_digest_contextos([contexto]),
        estado="en_proceso",
    )
    db_session.add(operacion)
    await db_session.flush()
    db_session.add(
        OperacionIdempotenteElegibilidadRece(
            operacion_id=int(operacion.id),
            empresa_id=contexto.empresa_id,
            punto_venta_id=contexto.punto_venta_id,
            ambiente=contexto.ambiente,
            elegibilidad_revision_id=contexto.elegibilidad_revision_id,
            punto_venta_revision_fiscal=contexto.punto_venta_revision_fiscal,
        )
    )
    await db_session.flush()
    db_session.add(
        PuntoVentaGuardaEmisionRece(
            token=token,
            fase="pre_arca",
            operacion_id=int(operacion.id),
            empresa_id=contexto.empresa_id,
            punto_venta_id=contexto.punto_venta_id,
            ambiente=contexto.ambiente,
            elegibilidad_revision_id=contexto.elegibilidad_revision_id,
            punto_venta_revision_fiscal=contexto.punto_venta_revision_fiscal,
        )
    )
    await db_session.commit()


@pytest.fixture
async def segundo_emisor(db_session: AsyncSession) -> Empresa:
    """Crear un segundo emisor para validar scoping admin."""
    emisor = Empresa(
        razon_social="Segundo Emisor",
        cuit="30123456789",
        condicion_iva="Exento",
        domicilio="Calle Falsa 123",
        localidad="Ciudad de Prueba",
        provincia="Buenos Aires",
        codigo_postal="1609",
        inicio_actividades=date(2018, 8, 1),
    )
    db_session.add(emisor)
    await db_session.commit()
    await db_session.refresh(emisor)
    return emisor


@pytest.fixture
async def punto_venta_demo(
    db_session: AsyncSession, test_empresa: Empresa
) -> PuntoVenta:
    """Crear un punto de venta asociado al primer emisor."""
    punto = PuntoVenta(
        numero=5,
        nombre="Webservices",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto)
    await db_session.commit()
    await db_session.refresh(punto)
    return punto


@pytest.mark.asyncio
async def test_admin_lista_puntos_venta_solo_del_emisor_activo(
    client: AsyncClient,
    admin_auth_headers: dict,
    segundo_emisor: Empresa,
    punto_venta_demo: PuntoVenta,
):
    """Un admin debe ver solo puntos del emisor indicado por X-Empresa-Id."""
    response = await client.get(
        "/api/puntos-venta",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segundo_emisor.id)},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_admin_crea_punto_venta_en_emisor_activo(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    segundo_emisor: Empresa,
):
    """La creacion admin debe asociarse al emisor activo, no a otro emisor."""
    response = await client.post(
        "/api/puntos-venta",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segundo_emisor.id)},
        json={"numero": 12, "nombre": "Produccion"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["numero"] == 12
    assert data["empresa_id"] == segundo_emisor.id
    revisiones = list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceRevision)
                .where(PuntoVentaElegibilidadReceRevision.punto_venta_id == data["id"])
                .order_by(PuntoVentaElegibilidadReceRevision.ambiente)
            )
        ).scalars()
    )
    assert [revision.ambiente for revision in revisiones] == [
        "homologacion",
        "produccion",
    ]
    assert {revision.estado for revision in revisiones} == {"no_verificado"}
    assert {revision.fuente for revision in revisiones} == {"alta_manual"}


@pytest.mark.asyncio
async def test_permisos_reservan_mutaciones_fiscales_al_admin(
    client: AsyncClient,
    auth_headers: dict[str, str],
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
) -> None:
    """El operador edita descripción, pero no crea, importa, borra ni cambia fiscal."""
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 14, "nombre": "Nombre inicial"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]

    alta_operador = await client.post(
        "/api/puntos-venta",
        headers=auth_headers,
        json={"numero": 15, "nombre": "Alta no autorizada"},
    )
    assert alta_operador.status_code == 403

    fiscal_operador = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=auth_headers,
        json={"sistema": "Factura electrónica - Web Services"},
    )
    assert fiscal_operador.status_code == 403

    importacion_operador = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=auth_headers,
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )
    assert importacion_operador.status_code == 403

    borrado_operador = await client.delete(
        f"/api/puntos-venta/{punto_id}",
        headers=auth_headers,
    )
    assert borrado_operador.status_code == 403

    descriptiva_operador = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=auth_headers,
        json={
            "nombre": "Nombre administrativo",
            "domicilio": "Domicilio descriptivo",
            "nombre_fantasia": "Fantasía descriptiva",
        },
    )
    assert descriptiva_operador.status_code == 200, descriptiva_operador.text
    assert descriptiva_operador.json()["revision_fiscal"] == 1

    fiscal_admin = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=admin_headers,
        json={"sistema": "Factura electrónica - Web Services"},
    )
    assert fiscal_admin.status_code == 200, fiscal_admin.text
    assert fiscal_admin.json()["revision_fiscal"] == 2

    borrado_admin = await client.delete(
        f"/api/puntos-venta/{punto_id}",
        headers=admin_headers,
    )
    assert borrado_admin.status_code == 204, borrado_admin.text

    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    await db_session.refresh(punto)
    assert punto.nombre == "Nombre administrativo"
    assert punto.sistema == "Factura electrónica - Web Services"
    assert punto.activo is False
    assert punto.revision_fiscal == 3
    assert (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == test_empresa.id,
                PuntoVenta.numero == 15,
            )
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_edicion_fiscal_incrementa_revision_e_invalida_heads(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """Un cambio fiscal usa CAS y crea dos heads nuevas cerradas."""
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_auth_headers,
        json={"numero": 13, "nombre": "Punto inicial"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]

    descriptiva = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=admin_auth_headers,
        json={"nombre": "Punto descriptivo"},
    )
    assert descriptiva.status_code == 200, descriptiva.text
    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    assert punto.revision_fiscal == 1

    fiscal = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=admin_auth_headers,
        json={"sistema": "Factura electrónica - Web Services"},
    )
    assert fiscal.status_code == 200, fiscal.text
    await db_session.refresh(punto)
    assert punto.revision_fiscal == 2

    revisiones = list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceRevision).where(
                    PuntoVentaElegibilidadReceRevision.punto_venta_id == punto_id
                )
            )
        ).scalars()
    )
    assert len(revisiones) == 4
    assert sum(revision.fuente == "edicion" for revision in revisiones) == 2
    heads = list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceActual).where(
                    PuntoVentaElegibilidadReceActual.punto_venta_id == punto_id
                )
            )
        ).scalars()
    )
    assert len(heads) == 2
    revisiones_por_id = {revision.id: revision for revision in revisiones}
    assert {revisiones_por_id[head.revision_actual_id].estado for head in heads} == {
        "no_verificado"
    }

    bloqueo = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=admin_auth_headers,
        json={"bloqueado": True},
    )
    assert bloqueo.status_code == 200, bloqueo.text
    await db_session.refresh(punto)
    assert punto.revision_fiscal == 3
    cantidad_tras_bloqueo = len(
        list(
            (
                await db_session.execute(
                    select(PuntoVentaElegibilidadReceRevision).where(
                        PuntoVentaElegibilidadReceRevision.punto_venta_id == punto_id
                    )
                )
            ).scalars()
        )
    )
    assert cantidad_tras_bloqueo == 4

    desactivacion = await client.put(
        f"/api/puntos-venta/{punto_id}",
        headers=admin_auth_headers,
        json={"activo": False},
    )
    assert desactivacion.status_code == 200, desactivacion.text
    await db_session.refresh(punto)
    assert punto.revision_fiscal == 4
    cantidad_tras_desactivacion = len(
        list(
            (
                await db_session.execute(
                    select(PuntoVentaElegibilidadReceRevision).where(
                        PuntoVentaElegibilidadReceRevision.punto_venta_id == punto_id
                    )
                )
            ).scalars()
        )
    )
    assert cantidad_tras_desactivacion == 6


@pytest.mark.asyncio
async def test_punto_venta_numero_unico_por_emisor(
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """La base debe impedir dos puntos con el mismo número en un emisor."""
    db_session.add_all(
        [
            PuntoVenta(
                numero=22, nombre="PV A", activo=True, empresa_id=test_empresa.id
            ),
            PuntoVenta(
                numero=22, nombre="PV B", activo=True, empresa_id=test_empresa.id
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_update_punto_venta_rechaza_numero_duplicado_por_emisor(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """La API no debe permitir duplicar el número al editar un punto."""
    punto_a = PuntoVenta(
        numero=31,
        nombre="PV A",
        activo=True,
        empresa_id=test_empresa.id,
    )
    punto_b = PuntoVenta(
        numero=32,
        nombre="PV B",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_a, punto_b])
    await db_session.commit()
    await db_session.refresh(punto_b)

    response = await client.put(
        f"/api/puntos-venta/{punto_b.id}",
        headers=admin_auth_headers,
        json={"numero": 31},
    )

    assert response.status_code == 400
    assert "Ya existe un punto de venta con el número 31" in response.json()["detail"]


@pytest.mark.parametrize(
    "respuesta_vacia",
    [False, True],
    ids=["excepcion", "respuesta-vacia"],
)
@pytest.mark.asyncio
async def test_importar_constancia_preserva_estado_si_falla_estado_arca(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch,
    respuesta_vacia: bool,
):
    """La importación no debe desbloquear puntos si no pudo consultar ARCA."""
    from app.api import puntos_venta as puntos_venta_api
    from app.services.constancia_puntos_venta_service import (
        DatosConstanciaPuntosVenta,
        PuntoVentaConstancia,
    )

    existente = PuntoVenta(
        numero=7,
        nombre="PV bloqueado",
        sistema="Factura Electronica - Web Services",
        es_webservice=True,
        bloqueado=True,
        fecha_baja="20260601",
        activo=False,
        fuente="arca_wsfe",
        empresa_id=test_empresa.id,
    )
    db_session.add(existente)
    await db_session.commit()
    await db_session.refresh(existente)

    def fake_extraer_texto(_contenido: bytes) -> str:
        return "texto constancia"

    def fake_parsear(_texto: str) -> DatosConstanciaPuntosVenta:
        return DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=7,
                    sistema="Factura Electronica - Web Services",
                    domicilio="Domicilio actualizado",
                    es_webservice=True,
                ),
                PuntoVentaConstancia(
                    numero=8,
                    sistema="Factura Electronica - Web Services",
                    domicilio="Domicilio nuevo",
                    es_webservice=True,
                ),
            ],
        )

    class ClienteWsfeVacio:
        """Representa la respuesta 602/sin resultados normalizada por WSFE."""

        async def fe_param_get_ptos_venta(self) -> list[object]:
            return []

    async def fail_get_wsfe_client(*_args, **_kwargs):
        if respuesta_vacia:
            return ClienteWsfeVacio()
        raise RuntimeError("ARCA no disponible")

    monkeypatch.setattr(
        puntos_venta_api, "extraer_texto_constancia_puntos_pdf", fake_extraer_texto
    )
    monkeypatch.setattr(
        puntos_venta_api, "parsear_constancia_puntos_venta", fake_parsear
    )
    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", fail_get_wsfe_client)

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["creados"] == 1
    assert data["actualizados"] == 1
    assert any("No se pudo consultar" in warning for warning in data["warnings"])

    await db_session.refresh(existente)
    assert existente.bloqueado is True
    assert existente.fecha_baja == "20260601"
    assert existente.activo is False
    assert existente.domicilio == "Domicilio actualizado"

    nuevo = (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == test_empresa.id,
                PuntoVenta.numero == 8,
            )
        )
    ).scalar_one()
    assert nuevo.activo is False
    assert nuevo.bloqueado is False
    assert nuevo.fecha_baja is None


@pytest.mark.asyncio
async def test_importar_constancia_rechaza_numero_fuera_de_rango_antes_de_arca(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un parser fuera de contrato no puede crear ni atestiguar el punto cero."""
    from app.api import puntos_venta as puntos_venta_api

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    consultas = 0

    async def contar_consulta(*_args: Any, **_kwargs: Any) -> dict[int, object]:
        nonlocal consultas
        consultas += 1
        return {}

    monkeypatch.setattr(
        puntos_venta_api,
        "extraer_texto_constancia_puntos_pdf",
        lambda _contenido: "texto constancia sintética",
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "parsear_constancia_puntos_venta",
        lambda _texto: DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=0,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "_obtener_estado_puntos_arca",
        contar_consulta,
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 400, response.text
    assert "número de punto de venta inválido" in response.json()["detail"]
    assert consultas == 0
    assert (
        await db_session.execute(select(PuntoVenta).where(PuntoVenta.numero == 0))
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_atestacion_productiva_exacta_es_visible_y_monotonica(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La atestación exacta promueve solo producción y cada carga crea revisión."""
    from app.core.config import settings

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 61, "nombre": "Punto por acreditar"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]
    datos = DatosConstanciaPuntosVenta(
        cuit=test_empresa.cuit,
        documento_emitido_en=HOY_RECE_PRUEBA,
        puntos_venta=[
            PuntoVentaConstancia(
                numero=61,
                sistema=SENAL_RECE_EXACTA,
                domicilio="FISCAL - 0001 - CALLE SINTÉTICA 123 - BUENOS AIRES",
                nombre_fantasia="PUNTO SINTÉTICO",
                es_webservice=True,
            )
        ],
    )
    _configurar_constancia_sintetica(
        monkeypatch,
        datos,
        estado_arca={61: {"bloqueado": False, "fecha_baja": None}},
    )

    respuestas = []
    for _ in range(2):
        response = await client.post(
            "/api/puntos-venta/importar-constancia",
            headers=admin_headers,
            data={"confirmar_procedencia_produccion": "true"},
            files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
        )
        assert response.status_code == 200, response.text
        respuestas.append(response)

    assert respuestas[0].json()["verificados_rece"] == 1
    assert respuestas[0].json()["no_verificados_rece"] == 0
    assert respuestas[0].json()["documento_emitido_en"] == "2026-08-09"
    assert respuestas[0].json()["vigente_hasta"] == "2026-08-16"

    listado = await client.get("/api/puntos-venta", headers=admin_headers)
    assert listado.status_code == 200, listado.text
    dto = next(item for item in listado.json() if item["id"] == punto_id)
    elegibilidad = dto["elegibilidad_rece"]
    assert dto["revision_fiscal"] == 3
    assert dto["usable_factuflow"] is True
    assert elegibilidad["ambiente"] == "produccion"
    assert elegibilidad["estado"] == "verificado_rece"
    assert elegibilidad["estado_efectivo"] == "verificado_rece"
    assert elegibilidad["fuente"] == "constancia_arca_atestada"
    assert elegibilidad["revision"] == 3
    assert elegibilidad["motivo"] is None
    assert set(elegibilidad) == CLAVES_PUBLICAS_ELEGIBILIDAD_RECE
    assert EVIDENCIA_PRIVADA_RECE.isdisjoint(dto)
    assert EVIDENCIA_PRIVADA_RECE.isdisjoint(elegibilidad)

    revisiones = await _revisiones_punto(db_session, punto_id)
    por_ambiente = {
        ambiente: [revision for revision in revisiones if revision.ambiente == ambiente]
        for ambiente in ("homologacion", "produccion")
    }
    assert [revision.revision for revision in por_ambiente["produccion"]] == [
        1,
        2,
        3,
    ]
    assert [revision.estado for revision in por_ambiente["produccion"]] == [
        "no_verificado",
        "verificado_rece",
        "verificado_rece",
    ]
    assert [revision.estado for revision in por_ambiente["homologacion"]] == [
        "no_verificado",
        "no_verificado",
        "no_verificado",
    ]
    revision_productiva = por_ambiente["produccion"][-1]
    assert revision_productiva.evidencia_sha256 is not None
    assert revision_productiva.empresa_cuit_snapshot == test_empresa.cuit
    assert revision_productiva.actor_usuario_id_snapshot is not None
    assert revision_productiva.evidencia_sha256 not in listado.text
    assert test_empresa.cuit not in listado.text

    monkeypatch.setattr(settings, "arca_env", "homologacion")
    listado_homologacion = await client.get(
        "/api/puntos-venta",
        headers=admin_headers,
    )
    assert listado_homologacion.status_code == 200, listado_homologacion.text
    dto_homologacion = next(
        item for item in listado_homologacion.json() if item["id"] == punto_id
    )
    assert dto_homologacion["usable_factuflow"] is False
    assert dto_homologacion["elegibilidad_rece"]["ambiente"] == "homologacion"
    assert dto_homologacion["elegibilidad_rece"]["estado_efectivo"] == "no_verificado"


@pytest.mark.asyncio
async def test_pdf_real_atestigua_ledger_rece_con_hash_del_archivo(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integra PDF, parser, API y ledger sin reemplazar la evidencia documental."""
    from app.api import puntos_venta as puntos_venta_api

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    contenido = HTML(
        string=f"""
            <pre>
            CONSTANCIA DE PUNTOS DE VENTA / EMISIÓN Y DOMICILIOS
            CUIT: EMISOR SINTÉTICO SIN DATOS REALES {test_empresa.cuit}
            PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
            00062 {SENAL_RECE_EXACTA}
            FISCAL - 0001 - CALLE SINTÉTICA 123 - BUENOS AIRES LABORATORIO
            09/08/2026
            </pre>
        """
    ).write_pdf()

    async def estado_arca_completo(
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[int, dict[str, str | bool | None]]:
        return {62: {"bloqueado": False, "fecha_baja": None}}

    monkeypatch.setattr(
        puntos_venta_api,
        "_obtener_estado_puntos_arca",
        estado_arca_completo,
    )
    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", contenido, "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["verificados_rece"] == 1
    assert response.json()["omitidos"] == 0
    punto = (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == test_empresa.id,
                PuntoVenta.numero == 62,
            )
        )
    ).scalar_one()
    revisiones = await _revisiones_punto(db_session, int(punto.id))
    productiva = next(
        revision
        for revision in revisiones
        if revision.ambiente == "produccion" and revision.revision == 2
    )
    assert productiva.estado == "verificado_rece"
    assert productiva.evidencia_sha256 == hashlib.sha256(contenido).hexdigest()
    assert (
        productiva.clasificador_version == ElegibilidadReceService.CLASIFICADOR_VERSION
    )


@pytest.mark.asyncio
async def test_atestacion_revalida_cuit_actual_del_emisor(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_admin: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una identidad cambiada antes del commit invalida toda la atestación."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    cuit_leido = test_empresa.cuit
    creada = await client.post(
        "/api/puntos-venta",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        json={
            "numero": 74,
            "nombre": "Punto con identidad concurrente",
            "sistema": SENAL_RECE_EXACTA,
            "es_webservice": True,
        },
    )
    assert creada.status_code == 201, creada.text
    punto = await db_session.get(PuntoVenta, creada.json()["id"])
    assert punto is not None
    punto_id = int(punto.id)

    test_empresa.cuit = "30999999995"
    await db_session.commit()

    with pytest.raises(ElegibilidadReceError, match="identidad fiscal"):
        await ElegibilidadReceService(
            db_session,
            hoy=HOY_RECE_PRUEBA,
        ).atestiguar_constancia_productiva(
            [
                AtestacionPuntoRece(
                    punto_venta=punto,
                    cambios={"sistema": SENAL_RECE_EXACTA},
                    sistema_constancia=SENAL_RECE_EXACTA,
                )
            ],
            empresa_id=int(test_empresa.id),
            empresa_cuit=cuit_leido,
            evidencia_sha256="c" * 64,
            documento_emitido_en=HOY_RECE_PRUEBA,
            actor_usuario_id=int(test_admin.id),
        )

    revisiones = await _revisiones_punto(db_session, punto_id)
    assert {revision.estado for revision in revisiones} == {"no_verificado"}
    punto_actual = await db_session.get(PuntoVenta, punto_id)
    assert punto_actual is not None
    assert punto_actual.revision_fiscal == 1


@pytest.mark.asyncio
async def test_importacion_revierte_punto_nuevo_si_cambia_cuit_antes_de_atestiguar(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un CUIT cambiado al final revierte el alta y todo su ledger inicial."""
    from app.api import puntos_venta as puntos_venta_api

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    empresa_id = int(test_empresa.id)
    cuit_original = test_empresa.cuit
    frontera_observada_sin_hijos = False
    orden_frontera: list[str] = []
    datos = DatosConstanciaPuntosVenta(
        cuit=cuit_original,
        documento_emitido_en=HOY_RECE_PRUEBA,
        puntos_venta=[
            PuntoVentaConstancia(
                numero=76,
                sistema=SENAL_RECE_EXACTA,
                es_webservice=True,
            )
        ],
    )

    async def cambiar_cuit_despues_de_validar(
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[int, dict[str, str | bool | None]]:
        orden_frontera.append("lectura_arca_finalizada")
        await db_session.execute(
            update(Empresa)
            .where(Empresa.id == empresa_id)
            .values(cuit="30777777778")
            .execution_options(synchronize_session=False)
        )
        return {76: {"bloqueado": False, "fecha_baja": None}}

    exigir_empresa_original = ElegibilidadReceService._exigir_empresa_cuit_actual

    async def exigir_empresa_antes_del_primer_hijo(
        servicio: ElegibilidadReceService,
        *,
        empresa_id: int,
        empresa_cuit: str,
    ) -> None:
        """Demuestra que el lock del emisor precede al alta y a su primer flush."""
        nonlocal frontera_observada_sin_hijos
        assert orden_frontera == ["lectura_arca_finalizada"]
        orden_frontera.append("empresa_bloqueada")
        assert not any(
            isinstance(objeto, PuntoVenta) and objeto.numero == 76
            for objeto in servicio.db.new
        )
        with servicio.db.no_autoflush:
            punto_id = await servicio.db.scalar(
                select(PuntoVenta.id).where(
                    PuntoVenta.empresa_id == empresa_id,
                    PuntoVenta.numero == 76,
                )
            )
        assert punto_id is None
        frontera_observada_sin_hijos = True
        await exigir_empresa_original(
            servicio,
            empresa_id=empresa_id,
            empresa_cuit=empresa_cuit,
        )

    monkeypatch.setattr(
        puntos_venta_api,
        "extraer_texto_constancia_puntos_pdf",
        lambda _contenido: "texto constancia sintética",
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "parsear_constancia_puntos_venta",
        lambda _texto: datos,
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "_obtener_estado_puntos_arca",
        cambiar_cuit_despues_de_validar,
    )
    monkeypatch.setattr(
        ElegibilidadReceService,
        "_exigir_empresa_cuit_actual",
        exigir_empresa_antes_del_primer_hijo,
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 409, response.text
    assert "identidad fiscal" in response.json()["detail"]
    assert frontera_observada_sin_hijos is True
    assert orden_frontera == ["lectura_arca_finalizada", "empresa_bloqueada"]
    punto = (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.numero == 76,
            )
        )
    ).scalar_one_or_none()
    assert punto is None
    empresa_actual = await db_session.get(Empresa, empresa_id)
    assert empresa_actual is not None
    await db_session.refresh(empresa_actual)
    assert empresa_actual.cuit == cuit_original


@pytest.mark.asyncio
async def test_contexto_rece_rechaza_snapshot_cuit_obsoleto(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_admin: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La emisión falla cerrado si el CUIT actual difiere del atestiguado."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    creada = await client.post(
        "/api/puntos-venta",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        json={
            "numero": 75,
            "nombre": "Punto con snapshot de CUIT",
            "sistema": SENAL_RECE_EXACTA,
            "es_webservice": True,
        },
    )
    assert creada.status_code == 201, creada.text
    punto = await db_session.get(PuntoVenta, creada.json()["id"])
    assert punto is not None
    servicio = ElegibilidadReceService(db_session, hoy=HOY_RECE_PRUEBA)
    await servicio.atestiguar_constancia_productiva(
        [
            AtestacionPuntoRece(
                punto_venta=punto,
                cambios={"sistema": SENAL_RECE_EXACTA},
                sistema_constancia=SENAL_RECE_EXACTA,
            )
        ],
        empresa_id=int(test_empresa.id),
        empresa_cuit=test_empresa.cuit,
        evidencia_sha256="d" * 64,
        documento_emitido_en=HOY_RECE_PRUEBA,
        actor_usuario_id=int(test_admin.id),
    )

    test_empresa.cuit = "30888888889"
    await db_session.commit()

    with pytest.raises(ElegibilidadReceError, match="cambio fiscal del emisor"):
        await servicio.exigir_contexto_actual(
            empresa_id=int(test_empresa.id),
            punto_venta_id=int(punto.id),
            ambiente="produccion",
        )


@pytest.mark.asyncio
async def test_constancia_completa_invalida_ausente_previamente_verificado(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_admin: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un presente se acredita y un ausente pierde vigencia en la misma carga."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    ids: dict[int, int] = {}
    for numero in (64, 65):
        creada = await client.post(
            "/api/puntos-venta",
            headers=admin_headers,
            json={
                "numero": numero,
                "nombre": f"Punto {numero}",
                "sistema": SENAL_RECE_EXACTA,
                "es_webservice": True,
            },
        )
        assert creada.status_code == 201, creada.text
        ids[numero] = creada.json()["id"]

    ausente = await db_session.get(PuntoVenta, ids[65])
    assert ausente is not None
    await ElegibilidadReceService(
        db_session,
        hoy=HOY_RECE_PRUEBA,
    ).atestiguar_constancia_productiva(
        [
            AtestacionPuntoRece(
                punto_venta=ausente,
                cambios={"sistema": SENAL_RECE_EXACTA},
                sistema_constancia=SENAL_RECE_EXACTA,
            )
        ],
        empresa_id=int(test_empresa.id),
        empresa_cuit=test_empresa.cuit,
        evidencia_sha256="a" * 64,
        documento_emitido_en=HOY_RECE_PRUEBA,
        actor_usuario_id=int(test_admin.id),
    )

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=64,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={64: {"bloqueado": False, "fecha_baja": None}},
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["verificados_rece"] == 1
    assert response.json()["desactivados_ausentes"] == 1
    assert any("no figuraron" in warning for warning in response.json()["warnings"])
    presente = await db_session.get(PuntoVenta, ids[64])
    assert presente is not None
    await db_session.refresh(presente)
    await db_session.refresh(ausente)
    assert presente.activo is True
    assert presente.revision_fiscal == 2
    assert ausente.activo is False
    assert ausente.revision_fiscal == 3

    revisiones_ausente = await _revisiones_punto(db_session, ids[65])
    productivas_ausente = [
        revision for revision in revisiones_ausente if revision.ambiente == "produccion"
    ]
    assert [revision.estado for revision in productivas_ausente] == [
        "no_verificado",
        "verificado_rece",
        "no_verificado",
    ]
    assert productivas_ausente[-1].fuente == "constancia_arca_atestada"

    listado = await client.get("/api/puntos-venta", headers=admin_headers)
    assert listado.status_code == 200, listado.text
    por_numero = {item["numero"]: item for item in listado.json()}
    assert por_numero[64]["usable_factuflow"] is True
    assert por_numero[64]["elegibilidad_rece"]["estado"] == "verificado_rece"
    assert por_numero[65]["usable_factuflow"] is False
    assert por_numero[65]["elegibilidad_rece"]["estado"] == "no_verificado"


@pytest.mark.asyncio
async def test_constancia_anterior_exacta_no_revierte_senal_generica_mas_nueva(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una señal exacta vieja no prevalece sobre evidencia genérica más nueva."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 75, "nombre": "Punto con precedencia documental"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=75,
                    sistema="Web Services",
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={75: {"bloqueado": False, "fecha_baja": None}},
    )
    nueva = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia-nueva.pdf", b"%PDF nueva", "application/pdf")},
    )
    assert nueva.status_code == 200, nueva.text
    assert nueva.json()["verificados_rece"] == 0
    assert nueva.json()["no_verificados_rece"] == 1

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=date(2026, 8, 8),
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=75,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={75: {"bloqueado": False, "fecha_baja": None}},
    )
    anterior = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={"confirmar_procedencia_produccion": "true"},
        files={
            "file": ("constancia-anterior.pdf", b"%PDF anterior", "application/pdf")
        },
    )

    assert anterior.status_code == 409, anterior.text
    assert "anterior a una evidencia" in anterior.json()["detail"]
    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    await db_session.refresh(punto)
    assert punto.sistema == "Web Services"
    assert punto.revision_fiscal == 2
    revisiones = await _revisiones_punto(db_session, punto_id)
    assert len(revisiones) == 4
    assert {
        revision.estado for revision in revisiones if revision.ambiente == "produccion"
    } == {"no_verificado"}


@pytest.mark.asyncio
async def test_constancia_anterior_no_invalida_presencia_documental_mas_nueva(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una ausencia inferida por un documento viejo no invalida presencia nueva."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    empresa_id = int(test_empresa.id)
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 76, "nombre": "Punto presente en documento nuevo"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=76,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={76: {"bloqueado": False, "fecha_baja": None}},
    )
    nueva = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia-nueva.pdf", b"%PDF nueva", "application/pdf")},
    )
    assert nueva.status_code == 200, nueva.text
    assert nueva.json()["verificados_rece"] == 1

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=date(2026, 8, 8),
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=77,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={77: {"bloqueado": False, "fecha_baja": None}},
    )
    anterior = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={"confirmar_procedencia_produccion": "true"},
        files={
            "file": ("constancia-anterior.pdf", b"%PDF anterior", "application/pdf")
        },
    )

    assert anterior.status_code == 409, anterior.text
    assert "anterior a una evidencia" in anterior.json()["detail"]
    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    await db_session.refresh(punto)
    assert punto.activo is True
    assert punto.revision_fiscal == 2
    assert (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.numero == 77,
            )
        )
    ).scalar_one_or_none() is None
    revisiones = await _revisiones_punto(db_session, punto_id)
    assert len(revisiones) == 4
    productivas = [
        revision for revision in revisiones if revision.ambiente == "produccion"
    ]
    assert [revision.estado for revision in productivas] == [
        "no_verificado",
        "verificado_rece",
    ]


@pytest.mark.parametrize(
    ("incluir_cuit", "warnings_parser"),
    [
        (False, []),
        (True, ["No se pudo interpretar una fila de la constancia."]),
    ],
    ids=["cuit-ausente", "fila-con-warning"],
)
@pytest.mark.asyncio
async def test_constancia_incompleta_no_infiere_ausencias(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_admin: Usuario,
    monkeypatch: pytest.MonkeyPatch,
    incluir_cuit: bool,
    warnings_parser: list[str],
) -> None:
    """Sin CUIT o con warnings no se desactiva un punto local omitido."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={
            "numero": 78,
            "nombre": "Punto que no debe inferirse ausente",
            "sistema": SENAL_RECE_EXACTA,
            "es_webservice": True,
        },
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]
    omitido = await db_session.get(PuntoVenta, punto_id)
    assert omitido is not None
    await ElegibilidadReceService(
        db_session,
        hoy=HOY_RECE_PRUEBA,
    ).atestiguar_constancia_productiva(
        [
            AtestacionPuntoRece(
                punto_venta=omitido,
                cambios={"sistema": SENAL_RECE_EXACTA},
                sistema_constancia=SENAL_RECE_EXACTA,
            )
        ],
        empresa_id=int(test_empresa.id),
        empresa_cuit=test_empresa.cuit,
        evidencia_sha256="c" * 64,
        documento_emitido_en=HOY_RECE_PRUEBA,
        actor_usuario_id=int(test_admin.id),
    )
    revisiones_antes = await _revisiones_punto(db_session, punto_id)

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit if incluir_cuit else None,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=79,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
            warnings=warnings_parser,
        ),
        estado_arca={79: {"bloqueado": False, "fecha_baja": None}},
    )
    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        files={"file": ("constancia-incompleta.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["omitidos"] == len(warnings_parser)
    assert response.json()["desactivados_ausentes"] == 0
    assert any(
        "No se desactivaron puntos ausentes" in warning
        for warning in response.json()["warnings"]
    )
    await db_session.refresh(omitido)
    assert omitido.activo is True
    assert omitido.revision_fiscal == 2
    revisiones_despues = await _revisiones_punto(db_session, punto_id)
    assert [revision.id for revision in revisiones_despues] == [
        revision.id for revision in revisiones_antes
    ]
    productiva = next(
        revision
        for revision in revisiones_despues
        if revision.ambiente == "produccion" and revision.revision == 2
    )
    assert productiva.estado == "verificado_rece"


@pytest.mark.parametrize(
    ("confirmar", "sistema"),
    [
        (False, SENAL_RECE_EXACTA),
        (True, "Web Services"),
        (True, f"{SENAL_RECE_EXACTA} adicional"),
    ],
    ids=["sin-confirmacion", "senal-generica", "coincidencia-parcial"],
)
@pytest.mark.asyncio
async def test_importacion_sin_autoridad_exacta_no_promueve_rece(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
    confirmar: bool,
    sistema: str,
) -> None:
    """Sin confirmación o sin señal exacta, el punto permanece no verificado."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 62, "nombre": "Punto cerrado"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]
    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=62,
                    sistema=sistema,
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={62: {"bloqueado": False, "fecha_baja": None}},
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={
            "confirmar_procedencia_produccion": str(confirmar).lower(),
        },
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["verificados_rece"] == 0
    assert response.json()["no_verificados_rece"] == 1
    listado = await client.get("/api/puntos-venta", headers=admin_headers)
    dto = next(item for item in listado.json() if item["id"] == punto_id)
    assert dto["usable_factuflow"] is False
    assert dto["elegibilidad_rece"]["estado"] == "no_verificado"
    assert dto["elegibilidad_rece"]["estado_efectivo"] == "no_verificado"


@pytest.mark.parametrize(
    ("ambiente", "documento_emitido_en", "status_esperado", "detalle"),
    [
        ("produccion", None, 400, "fecha documental válida"),
        ("produccion", date(2026, 8, 10), 409, "no puede ser futura"),
        ("produccion", date(2026, 8, 1), 409, "más de siete días"),
        ("homologacion", HOY_RECE_PRUEBA, 409, "servidor configurado para producción"),
    ],
    ids=["fecha-ausente", "fecha-futura", "fecha-vencida", "homologacion"],
)
@pytest.mark.asyncio
async def test_atestacion_invalida_falla_cerrado_sin_escrituras(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
    ambiente: str,
    documento_emitido_en: date | None,
    status_esperado: int,
    detalle: str,
) -> None:
    """Fecha ausente/futura/vencida o homologación no alteran punto ni ledger."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente=ambiente)
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 63, "nombre": "Punto sin atestiguar"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]
    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=documento_emitido_en,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=63,
                    sistema=SENAL_RECE_EXACTA,
                    domicilio="Domicilio que no debe persistirse",
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={63: {"bloqueado": False, "fecha_baja": None}},
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == status_esperado, response.text
    assert detalle in response.json()["detail"]
    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    await db_session.refresh(punto)
    assert punto.revision_fiscal == 1
    assert punto.sistema is None
    assert punto.domicilio is None
    revisiones = await _revisiones_punto(db_session, punto_id)
    assert len(revisiones) == 2
    assert {revision.estado for revision in revisiones} == {"no_verificado"}


@pytest.mark.asyncio
async def test_atestacion_con_warning_aborta_antes_de_consultar_arca(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una fila ilegible impide acreditación parcial, consulta técnica y escritura."""
    from app.api import puntos_venta as puntos_venta_api

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    consultas = 0

    async def contar_consulta(*_args: Any, **_kwargs: Any) -> dict[int, object]:
        nonlocal consultas
        consultas += 1
        return {}

    monkeypatch.setattr(
        puntos_venta_api,
        "extraer_texto_constancia_puntos_pdf",
        lambda _contenido: "texto constancia sintética",
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "parsear_constancia_puntos_venta",
        lambda _texto: DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=66,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
            warnings=["No se pudo interpretar otra fila de la constancia."],
        ),
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "_obtener_estado_puntos_arca",
        contar_consulta,
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 400, response.text
    assert "forma completa" in response.json()["detail"]
    assert consultas == 0
    assert (
        await db_session.execute(select(PuntoVenta).where(PuntoVenta.numero == 66))
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_fecha_documental_ambigua_aborta_antes_de_consultar_arca(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fechas distintas no eligen una por posición ni alcanzan la lectura WSFE."""
    from app.api import puntos_venta as puntos_venta_api

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    consultas = 0

    async def contar_consulta(*_args: Any, **_kwargs: Any) -> dict[int, object]:
        nonlocal consultas
        consultas += 1
        return {}

    texto = f"""
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT: ENTIDAD DE PRUEBA {test_empresa.cuit}
    PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
    00067 {SENAL_RECE_EXACTA}
    FISCAL - 0001 - CALLE FALSA 123 - BUENOS AIRES QA
    08/08/2026
    09/08/2026
    """
    monkeypatch.setattr(
        puntos_venta_api,
        "extraer_texto_constancia_puntos_pdf",
        lambda _contenido: texto,
    )
    monkeypatch.setattr(
        puntos_venta_api,
        "_obtener_estado_puntos_arca",
        contar_consulta,
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 400, response.text
    assert "fechas documentales ambiguas" in response.json()["detail"]
    assert consultas == 0
    assert (
        await db_session.execute(select(PuntoVenta).where(PuntoVenta.numero == 67))
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_feparam_omite_punto_de_constancia_y_lo_deja_inactivo(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una respuesta WSFE completa sin el punto no conserva actividad permisiva."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={
            "numero": 68,
            "nombre": "Punto omitido por WSFE",
        },
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]
    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=68,
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                )
            ],
        ),
        estado_arca={99999: {"bloqueado": False, "fecha_baja": None}},
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=admin_headers,
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["desactivados_ausentes"] == 0
    assert any(
        "consulta técnica WSFE" in warning for warning in response.json()["warnings"]
    )
    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    await db_session.refresh(punto)
    assert punto.activo is False
    assert punto.revision_fiscal == 2
    revisiones = await _revisiones_punto(db_session, punto_id)
    assert {revision.estado for revision in revisiones} == {"no_verificado"}


@pytest.mark.asyncio
async def test_sincronizacion_arca_es_admin_fail_closed_y_monotonica(
    client: AsyncClient,
    auth_headers: dict[str, str],
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_admin: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync preserva RECE idéntico, cierra ausentes y no promueve puntos nuevos."""
    from app.api import puntos_venta as puntos_venta_api

    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    puntos: dict[int, PuntoVenta] = {}
    for numero in (69, 70):
        punto = PuntoVenta(
            numero=numero,
            nombre=f"Punto {numero}",
            sistema=SENAL_RECE_EXACTA,
            es_webservice=True,
            bloqueado=False,
            fecha_baja=None,
            fuente="arca_wsfe",
            activo=True,
            empresa_id=test_empresa.id,
        )
        db_session.add(punto)
        await ElegibilidadReceService(
            db_session,
            hoy=HOY_RECE_PRUEBA,
        ).crear_contextos_iniciales_no_verificados(
            punto,
            creado_por_usuario_id=int(test_admin.id),
            fuente="sincronizacion_wsfe",
        )
        puntos[numero] = punto
    await db_session.commit()
    await ElegibilidadReceService(
        db_session,
        hoy=HOY_RECE_PRUEBA,
    ).atestiguar_constancia_productiva(
        [
            AtestacionPuntoRece(
                punto_venta=punto,
                cambios={"sistema": SENAL_RECE_EXACTA},
                sistema_constancia=SENAL_RECE_EXACTA,
            )
            for punto in puntos.values()
        ],
        empresa_id=int(test_empresa.id),
        empresa_cuit=test_empresa.cuit,
        evidencia_sha256="b" * 64,
        documento_emitido_en=HOY_RECE_PRUEBA,
        actor_usuario_id=int(test_admin.id),
    )

    class ClienteWsfeSintetico:
        """Doble mínimo de la lectura técnica de puntos ARCA."""

        async def fe_param_get_ptos_venta(self) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    numero=69,
                    emision_tipo="CAE - RECE",
                    bloqueado="N",
                    fecha_baja=None,
                ),
                SimpleNamespace(
                    numero=71,
                    emision_tipo="CAE - Factura electrónica",
                    bloqueado="N",
                    fecha_baja=None,
                ),
            ]

    consultas = 0

    async def fake_get_wsfe_client(*_args: Any, **_kwargs: Any) -> ClienteWsfeSintetico:
        nonlocal consultas
        consultas += 1
        return ClienteWsfeSintetico()

    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", fake_get_wsfe_client)
    operador = await client.post(
        "/api/puntos-venta/sincronizar-arca",
        headers=auth_headers,
    )
    assert operador.status_code == 403
    assert consultas == 0

    response = await client.post(
        "/api/puntos-venta/sincronizar-arca",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "total_arca": 2,
        "nuevos": 1,
        "existentes": 1,
        "actualizados": 0,
        "desactivados_ausentes": 1,
    }
    assert consultas == 1
    await db_session.refresh(puntos[69])
    await db_session.refresh(puntos[70])
    assert puntos[69].activo is True
    assert puntos[69].revision_fiscal == 2
    assert puntos[70].activo is False
    assert puntos[70].revision_fiscal == 3
    nuevo = (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == test_empresa.id,
                PuntoVenta.numero == 71,
            )
        )
    ).scalar_one()
    assert nuevo.activo is True
    assert nuevo.revision_fiscal == 1

    productivas_presentes = [
        revision
        for revision in await _revisiones_punto(db_session, int(puntos[69].id))
        if revision.ambiente == "produccion"
    ]
    productivas_ausentes = [
        revision
        for revision in await _revisiones_punto(db_session, int(puntos[70].id))
        if revision.ambiente == "produccion"
    ]
    assert [revision.estado for revision in productivas_presentes] == [
        "no_verificado",
        "verificado_rece",
    ]
    assert [revision.estado for revision in productivas_ausentes] == [
        "no_verificado",
        "verificado_rece",
        "no_verificado",
    ]
    assert {
        revision.estado
        for revision in await _revisiones_punto(db_session, int(nuevo.id))
    } == {"no_verificado"}


@pytest.mark.asyncio
async def test_sincronizacion_arca_vacia_no_desactiva_puntos_locales(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin resultados WSFE no hay evidencia suficiente para inferir ausencias."""
    from app.api import puntos_venta as puntos_venta_api

    admin_headers = _headers_admin_emisor(admin_auth_headers, test_empresa)
    creada = await client.post(
        "/api/puntos-venta",
        headers=admin_headers,
        json={"numero": 81, "nombre": "Punto que debe preservarse"},
    )
    assert creada.status_code == 201, creada.text
    punto_id = creada.json()["id"]

    class ClienteWsfeVacio:
        """Doble de la respuesta sin resultados de FEParamGetPtosVenta."""

        async def fe_param_get_ptos_venta(self) -> list[object]:
            return []

    async def fake_get_wsfe_client(*_args: Any, **_kwargs: Any) -> ClienteWsfeVacio:
        return ClienteWsfeVacio()

    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", fake_get_wsfe_client)
    response = await client.post(
        "/api/puntos-venta/sincronizar-arca",
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text
    assert "no informó puntos de venta" in response.json()["detail"]
    punto = await db_session.get(PuntoVenta, punto_id)
    assert punto is not None
    await db_session.refresh(punto)
    assert punto.activo is True
    assert punto.revision_fiscal == 1


@pytest.mark.asyncio
async def test_sincronizacion_con_guarda_ausente_revierte_todo(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_user: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una guarda de un ausente revierte alta nueva y cambio técnico presente."""
    from app.api import puntos_venta as puntos_venta_api

    presente = PuntoVenta(
        numero=72,
        nombre="Presente",
        es_webservice=True,
        activo=True,
        empresa_id=test_empresa.id,
    )
    ausente = PuntoVenta(
        numero=73,
        nombre="Ausente con guarda",
        es_webservice=True,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([presente, ausente])
    service = ElegibilidadReceService(db_session)
    await service.crear_contextos_iniciales_no_verificados(presente)
    await service.crear_contextos_iniciales_no_verificados(ausente)
    await db_session.commit()
    empresa_id = int(test_empresa.id)
    await _crear_guarda_rece_activa(
        db_session,
        punto=ausente,
        usuario=test_user,
        idempotency_key="sync-atomica-guarda-ausente",
        token="9" * 64,
    )

    class ClienteWsfeSintetico:
        """Doble con un punto cambiado y otro nuevo."""

        async def fe_param_get_ptos_venta(self) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    numero=72,
                    emision_tipo="CAE - RECE",
                    bloqueado="S",
                    fecha_baja=None,
                ),
                SimpleNamespace(
                    numero=74,
                    emision_tipo="CAE - RECE",
                    bloqueado="N",
                    fecha_baja=None,
                ),
            ]

    async def fake_get_wsfe_client(*_args: Any, **_kwargs: Any) -> ClienteWsfeSintetico:
        return ClienteWsfeSintetico()

    monkeypatch.setattr(puntos_venta_api, "get_wsfe_client", fake_get_wsfe_client)
    response = await client.post(
        "/api/puntos-venta/sincronizar-arca",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
    )

    assert response.status_code == 409, response.text
    assert "solicitud fiscal activa" in response.json()["detail"]
    await db_session.refresh(presente)
    await db_session.refresh(ausente)
    assert presente.bloqueado is False
    assert presente.activo is True
    assert presente.revision_fiscal == 1
    assert ausente.activo is True
    assert ausente.revision_fiscal == 1
    assert (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.numero == 74,
            )
        )
    ).scalar_one_or_none() is None
    revisiones = list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceRevision).where(
                    PuntoVentaElegibilidadReceRevision.punto_venta_id.in_(
                        [presente.id, ausente.id]
                    )
                )
            )
        ).scalars()
    )
    assert len(revisiones) == 4


@pytest.mark.asyncio
async def test_importar_constancia_con_guarda_aborta_todo_el_archivo(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa: Empresa,
    test_user: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La guarda de un ausente revierte altas y atestaciones del archivo."""
    _configurar_reloj_y_ambiente_rece(monkeypatch, ambiente="produccion")
    primero = PuntoVenta(
        numero=51,
        nombre="Primero",
        es_webservice=True,
        activo=True,
        empresa_id=test_empresa.id,
    )
    segundo = PuntoVenta(
        numero=52,
        nombre="Segundo",
        es_webservice=True,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([primero, segundo])
    service = ElegibilidadReceService(db_session)
    await service.crear_contextos_iniciales_no_verificados(primero)
    await service.crear_contextos_iniciales_no_verificados(segundo)
    await db_session.commit()
    empresa_id = int(test_empresa.id)
    await _crear_guarda_rece_activa(
        db_session,
        punto=segundo,
        usuario=test_user,
        idempotency_key="importacion-atomica-guarda",
        token="8" * 64,
    )

    _configurar_constancia_sintetica(
        monkeypatch,
        DatosConstanciaPuntosVenta(
            cuit=test_empresa.cuit,
            documento_emitido_en=HOY_RECE_PRUEBA,
            puntos_venta=[
                PuntoVentaConstancia(
                    numero=50,
                    sistema=SENAL_RECE_EXACTA,
                    domicilio="Domicilio nuevo",
                    es_webservice=True,
                ),
                PuntoVentaConstancia(
                    numero=primero.numero,
                    sistema=SENAL_RECE_EXACTA,
                    domicilio="Domicilio cambiado 1",
                    es_webservice=True,
                ),
            ],
        ),
        estado_arca={
            50: {"bloqueado": False, "fecha_baja": None},
            51: {"bloqueado": False, "fecha_baja": None},
        },
    )

    response = await client.post(
        "/api/puntos-venta/importar-constancia",
        headers=_headers_admin_emisor(admin_auth_headers, test_empresa),
        data={"confirmar_procedencia_produccion": "true"},
        files={"file": ("constancia.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 409
    assert "solicitud fiscal activa" in response.json()["detail"]
    await db_session.refresh(primero)
    await db_session.refresh(segundo)
    assert primero.revision_fiscal == 1
    assert primero.sistema is None
    assert primero.domicilio is None
    assert segundo.revision_fiscal == 1
    assert segundo.activo is True
    nuevo = (
        await db_session.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.numero == 50,
            )
        )
    ).scalar_one_or_none()
    assert nuevo is None
    revisiones = list(
        (
            await db_session.execute(
                select(PuntoVentaElegibilidadReceRevision).where(
                    PuntoVentaElegibilidadReceRevision.punto_venta_id.in_(
                        [primero.id, segundo.id]
                    )
                )
            )
        ).scalars()
    )
    assert len(revisiones) == 4
