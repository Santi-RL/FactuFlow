"""Regresiones SQLite para la integridad fiscal persistida de PF-01B."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comprobante import (
    ESTADO_COMPROBANTE_AUTORIZADO,
    ESTADOS_COMPROBANTE,
    Comprobante,
)
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import (
    ESTADOS_INTENTO_FISCAL,
    ESTADOS_INTENTO_FISCAL_BLOQUEANTES,
    ESTADOS_RESERVA_FISCAL_ACTIVA,
    PREDICADO_RESERVA_FISCAL_ACTIVA,
    IntentoEmisionFiscal,
)
from app.models.punto_venta import PuntoVenta
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService


CAE_SINTETICO = "12345678901234"
FECHA_FISCAL_SINTETICA = date(2026, 7, 13)


async def _crear_punto_venta(
    db_session: AsyncSession,
    empresa: Empresa,
) -> PuntoVenta:
    """Crea un punto de venta sintético para las pruebas de persistencia."""
    punto_venta = PuntoVenta(
        numero=41,
        nombre="Punto sintético",
        es_webservice=True,
        empresa_id=empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()
    await db_session.refresh(punto_venta)
    return punto_venta


def _crear_intento(
    empresa: Empresa,
    punto_venta: PuntoVenta,
    *,
    estado: str,
    numero_planificado: int = 101,
) -> IntentoEmisionFiscal:
    """Construye un intento fiscal sintético con estado controlado."""
    return IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=punto_venta.numero,
        numero_planificado=numero_planificado,
        fecha_emision=FECHA_FISCAL_SINTETICA,
        total=Decimal("121.00"),
        payload_hash="a" * 64,
        huella_logica="b" * 64,
        estado=estado,
        empresa_id=empresa.id,
        punto_venta_id=punto_venta.id,
    )


def _crear_comprobante(
    empresa: Empresa,
    punto_venta: PuntoVenta,
    *,
    estado: str,
    numero: int = 201,
    cae: str | None = None,
    cae_vencimiento: date | None = None,
) -> Comprobante:
    """Construye un comprobante sintético con semántica CAE explícita."""
    return Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=numero,
        fecha_emision=FECHA_FISCAL_SINTETICA,
        subtotal=Decimal("100.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("21.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("121.00"),
        cae=cae,
        cae_vencimiento=cae_vencimiento,
        estado=estado,
        moneda="PES",
        cotizacion=Decimal("1.000000"),
        empresa_id=empresa.id,
        punto_venta_id=punto_venta.id,
    )


def test_vocabularios_y_predicado_comparten_fuente_canonica() -> None:
    """El servicio y el índice parcial deben usar los estados del modelo."""
    assert IdempotenciaFiscalService.ESTADOS_INTENTO_ACTIVOS == (
        ESTADOS_RESERVA_FISCAL_ACTIVA
    )
    assert IdempotenciaFiscalService.ESTADOS_INTENTO_BLOQUEANTES == (
        ESTADOS_INTENTO_FISCAL_BLOQUEANTES
    )
    assert all(
        repr(estado) in PREDICADO_RESERVA_FISCAL_ACTIVA
        for estado in ESTADOS_RESERVA_FISCAL_ACTIVA
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ESTADOS_INTENTO_FISCAL)
async def test_intento_acepta_cada_estado_canonico(
    db_session: AsyncSession,
    test_empresa: Empresa,
    estado: str,
) -> None:
    """Cada estado canónico de intento debe persistirse."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(_crear_intento(test_empresa, punto_venta, estado=estado))

    await db_session.commit()


@pytest.mark.asyncio
async def test_intento_rechaza_estado_desconocido(
    db_session: AsyncSession,
    test_empresa: Empresa,
) -> None:
    """La base debe rechazar estados de intento fuera del vocabulario."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(
        _crear_intento(test_empresa, punto_venta, estado="estado_inexistente")
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ESTADOS_RESERVA_FISCAL_ACTIVA)
async def test_reserva_activa_impide_numero_duplicado(
    db_session: AsyncSession,
    test_empresa: Empresa,
    estado: str,
) -> None:
    """Todo estado activo debe conservar la exclusividad del número."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(_crear_intento(test_empresa, punto_venta, estado=estado))
    await db_session.commit()

    db_session.add(_crear_intento(test_empresa, punto_venta, estado=estado))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ("rechazado_arca", "fallido_verificado"))
async def test_estado_terminal_libera_numero_planificado(
    db_session: AsyncSession,
    test_empresa: Empresa,
    estado: str,
) -> None:
    """Los estados terminales verificados deben permitir reutilizar el número."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(_crear_intento(test_empresa, punto_venta, estado=estado))
    await db_session.commit()

    db_session.add(_crear_intento(test_empresa, punto_venta, estado="en_proceso"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_comprobante_acepta_estados_con_semantica_cae_valida(
    db_session: AsyncSession,
    test_empresa: Empresa,
) -> None:
    """Cada estado canónico debe respetar su contrato persistido de CAE."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)

    for numero, estado in enumerate(ESTADOS_COMPROBANTE, start=201):
        autorizado = estado == ESTADO_COMPROBANTE_AUTORIZADO
        db_session.add(
            _crear_comprobante(
                test_empresa,
                punto_venta,
                estado=estado,
                numero=numero,
                cae=CAE_SINTETICO if autorizado else None,
                cae_vencimiento=FECHA_FISCAL_SINTETICA if autorizado else None,
            )
        )

    await db_session.commit()


@pytest.mark.asyncio
async def test_comprobante_rechaza_estado_desconocido(
    db_session: AsyncSession,
    test_empresa: Empresa,
) -> None:
    """La base debe rechazar estados de comprobante fuera del vocabulario."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(
        _crear_comprobante(
            test_empresa,
            punto_venta,
            estado="estado_inexistente",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cae", "cae_vencimiento"),
    (
        (None, FECHA_FISCAL_SINTETICA),
        ("1234567890123", FECHA_FISCAL_SINTETICA),
        (CAE_SINTETICO, None),
    ),
)
async def test_autorizado_requiere_cae_completo(
    db_session: AsyncSession,
    test_empresa: Empresa,
    cae: str | None,
    cae_vencimiento: date | None,
) -> None:
    """Un autorizado sin CAE completo debe ser rechazado por la base."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(
        _crear_comprobante(
            test_empresa,
            punto_venta,
            estado=ESTADO_COMPROBANTE_AUTORIZADO,
            cae=cae,
            cae_vencimiento=cae_vencimiento,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cae", "cae_vencimiento"),
    (
        (CAE_SINTETICO, None),
        (None, FECHA_FISCAL_SINTETICA),
        (CAE_SINTETICO, FECHA_FISCAL_SINTETICA),
    ),
)
async def test_no_autorizado_rechaza_datos_cae(
    db_session: AsyncSession,
    test_empresa: Empresa,
    cae: str | None,
    cae_vencimiento: date | None,
) -> None:
    """Un estado no autorizado no puede conservar datos de autorización."""
    punto_venta = await _crear_punto_venta(db_session, test_empresa)
    db_session.add(
        _crear_comprobante(
            test_empresa,
            punto_venta,
            estado="pendiente",
            cae=cae,
            cae_vencimiento=cae_vencimiento,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
