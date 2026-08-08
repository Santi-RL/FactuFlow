"""Pruebas del inventario legacy de solo lectura de PF-19A."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import app.models  # noqa: F401
import app.scripts.pf19_legacy_inventory as pf19_cli
import app.services.inventario_legacy_pf19_service as inventario_module
import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base, _habilitar_foreign_keys_sqlite
from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.scripts.pf19_legacy_inventory import construir_parser
from app.services.inventario_legacy_pf19_service import (
    FiltrosInventarioLegacyPF19,
    InventarioLegacyPF19Error,
    MAX_REGISTROS_INVENTARIO_PF19,
    _clasificar_referencia,
    _clasificar_registro,
    activar_transaccion_solo_lectura,
    construir_consulta_inventario,
    inventariar_legacy_pf19,
)


FIRMA_GLOBAL_10005 = (
    "Error del servicio ARCA: ARCA devolvió errores globales al solicitar CAE: "
    "[10005] El punto de venta debe ser RECE"
)
CAE_SINTETICO_NO_REAL = "99999999999999"


async def _crear_engine_sintetico(
    tmp_path: Path,
    *,
    habilitar_claves_foraneas: bool = True,
) -> AsyncEngine:
    """Crea una SQLite temporal separada del engine de la aplicación."""
    database_path = tmp_path / "pf19-inventario.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        echo=False,
    )
    if habilitar_claves_foraneas:
        event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def _sembrar_candidatos(engine: AsyncEngine) -> int:
    """Inserta intentos sintéticos sin CAE ni comprobantes."""
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        empresa = Empresa(
            razon_social="Empresa sintética",
            cuit="20123456789",
            condicion_iva="RI",
            domicilio="Calle sintética 123",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        punto = PuntoVenta(
            numero=7,
            nombre="Web Services sintético",
            sistema="Web Services",
            fuente="arca_wsfe",
            es_webservice=True,
            bloqueado=False,
            activo=True,
            empresa=empresa,
        )
        session.add_all([empresa, punto])
        await session.flush()

        operacion = OperacionIdempotente(
            idempotency_key="sintetica-1",
            tipo_operacion="procesar_lote",
            payload_hash="a" * 64,
            estado="requiere_reconciliacion",
            response_json={"errores": [FIRMA_GLOBAL_10005]},
            empresa_id=empresa.id,
        )
        lote = LoteComprobante(
            nombre_archivo="sintetico.xlsx",
            archivo_hash="b" * 64,
            estado="requiere_reconciliacion",
            empresa_id=empresa.id,
        )
        session.add_all([operacion, lote])
        await session.flush()
        grupo = LoteComprobanteGrupo(
            comprobante_ref="grupo-1",
            orden=1,
            estado="requiere_reconciliacion",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            lote_id=lote.id,
        )
        session.add(grupo)
        await session.flush()
        session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=1,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="c" * 64,
                huella_logica="d" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_batch_sin_respuesta",
                operacion_id=operacion.id,
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            )
        )

        operacion_incierta = OperacionIdempotente(
            idempotency_key="sintetica-2",
            tipo_operacion="emitir_comprobante",
            payload_hash="e" * 64,
            estado="requiere_reconciliacion",
            response_json={
                "errores": [
                    "texto libre 10005",
                    "[10005] sin prefijo global",
                    "[100050] código diferente",
                ],
                "dato_no_error": FIRMA_GLOBAL_10005,
            },
            empresa_id=empresa.id,
        )
        session.add(operacion_incierta)
        await session.flush()
        session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=11,
                punto_venta_numero=7,
                numero_planificado=1,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("100.00"),
                payload_hash="f" * 64,
                huella_logica="1" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                operacion_id=operacion_incierta.id,
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
            )
        )

        operacion_inconsistente = OperacionIdempotente(
            idempotency_key="sintetica-3",
            tipo_operacion="emitir_comprobante",
            payload_hash="2" * 64,
            estado="fallido",
            response_json={"errores": [FIRMA_GLOBAL_10005]},
            empresa_id=empresa.id,
        )
        session.add(operacion_inconsistente)
        await session.flush()
        session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=1,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="3" * 64,
                huella_logica="4" * 64,
                estado="rechazado_arca",
                categoria_error="arca_respuesta_incierta",
                operacion_id=operacion_inconsistente.id,
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
            )
        )

        operacion_grupo_con_cae = OperacionIdempotente(
            idempotency_key="sintetica-4",
            tipo_operacion="procesar_lote",
            payload_hash="5" * 64,
            estado="requiere_reconciliacion",
            empresa_id=empresa.id,
        )
        lote_grupo_con_cae = LoteComprobante(
            nombre_archivo="sintetico-contradictorio.xlsx",
            archivo_hash="6" * 64,
            estado="requiere_reconciliacion",
            empresa_id=empresa.id,
        )
        session.add_all([operacion_grupo_con_cae, lote_grupo_con_cae])
        await session.flush()
        grupo_con_cae = LoteComprobanteGrupo(
            comprobante_ref="grupo-contradictorio",
            orden=1,
            estado="autorizado_externo",
            tipo_comprobante=1,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            lote_id=lote_grupo_con_cae.id,
        )
        session.add(grupo_con_cae)
        await session.flush()
        session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=1,
                punto_venta_numero=7,
                numero_planificado=2,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="7" * 64,
                huella_logica="8" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_batch_sin_respuesta",
                operacion_id=operacion_grupo_con_cae.id,
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                lote_id=lote_grupo_con_cae.id,
                grupo_id=grupo_con_cae.id,
            )
        )

        empresa_ajena = Empresa(
            razon_social="Otra empresa sintética",
            cuit="20999999991",
            condicion_iva="RI",
            domicilio="Otra calle sintética 456",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        session.add(empresa_ajena)
        await session.flush()
        operacion_ajena = OperacionIdempotente(
            idempotency_key="sintetica-ajena",
            tipo_operacion="emitir_comprobante",
            payload_hash="9" * 64,
            estado="requiere_reconciliacion",
            response_json={"errores": [FIRMA_GLOBAL_10005]},
            empresa_id=empresa_ajena.id,
        )
        session.add(operacion_ajena)
        await session.flush()
        session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=3,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="a1" * 32,
                huella_logica="b1" * 32,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                operacion_id=operacion_ajena.id,
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
            )
        )
        await session.commit()
        return int(empresa.id)


async def _sembrar_corrupcion_cruzada(engine: AsyncEngine) -> int:
    """Crea relaciones fiscales cruzadas sin usar datos reales ni romper FKs."""
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        empresa_propia = Empresa(
            razon_social="Emisor propio sintético",
            cuit="20111111112",
            condicion_iva="RI",
            domicilio="Calle propia 100",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        empresa_ajena = Empresa(
            razon_social="Emisor ajeno sintético",
            cuit="20222222223",
            condicion_iva="RI",
            domicilio="Calle ajena 200",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        punto_propio = PuntoVenta(
            numero=7,
            nombre="Punto propio sintético",
            sistema="Web Services",
            es_webservice=True,
            bloqueado=False,
            activo=True,
            empresa=empresa_propia,
        )
        punto_ajeno = PuntoVenta(
            numero=7,
            nombre="Punto ajeno sintético",
            sistema="Web Services",
            es_webservice=True,
            bloqueado=False,
            activo=True,
            empresa=empresa_ajena,
        )
        session.add_all([empresa_propia, empresa_ajena, punto_propio, punto_ajeno])
        await session.flush()

        comprobantes_ajenos = [
            Comprobante(
                tipo_comprobante=6,
                concepto=1,
                numero=numero,
                fecha_emision=date(2026, 8, 8),
                subtotal=Decimal("100.00"),
                descuento=Decimal("0"),
                iva_21=Decimal("21.00"),
                iva_10_5=Decimal("0"),
                iva_27=Decimal("0"),
                otros_impuestos=Decimal("0"),
                total=Decimal("121.00"),
                cae=f"99999999999{numero:03d}",
                cae_vencimiento=date(2026, 8, 18),
                estado="autorizado",
                empresa_id=empresa_ajena.id,
                punto_venta_id=punto_ajeno.id,
            )
            for numero in (1, 2)
        ]
        comprobantes_ajenos[1].numero = 102
        comprobantes_ajenos[1].punto_venta_id = punto_propio.id
        comprobante_grupo_numero_incorrecto = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=999,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae="88888888888999",
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_propio.id,
        )
        comprobante_grupo_punto_incorrecto = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=104,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae="88888888888104",
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_ajeno.id,
        )
        comprobante_grupo_tipo_incorrecto = Comprobante(
            tipo_comprobante=11,
            concepto=1,
            numero=105,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae="88888888888105",
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_propio.id,
        )
        comprobante_grupo_sin_numero_planificado = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=106,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae="88888888888106",
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_propio.id,
        )
        lote_propio = LoteComprobante(
            nombre_archivo="lote-propio-sintetico.xlsx",
            archivo_hash="e" * 64,
            estado="requiere_reconciliacion",
            empresa_id=empresa_propia.id,
        )
        lote_ajeno = LoteComprobante(
            nombre_archivo="lote-ajeno-sintetico.xlsx",
            archivo_hash="f" * 64,
            estado="requiere_reconciliacion",
            empresa_id=empresa_ajena.id,
        )
        session.add_all(
            [
                *comprobantes_ajenos,
                comprobante_grupo_numero_incorrecto,
                comprobante_grupo_punto_incorrecto,
                comprobante_grupo_tipo_incorrecto,
                comprobante_grupo_sin_numero_planificado,
                lote_propio,
                lote_ajeno,
            ]
        )
        await session.flush()

        grupo_lote_ajeno = LoteComprobanteGrupo(
            comprobante_ref="GRUPO-LOTE-AJENO",
            orden=1,
            estado="autorizado",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            comprobante_id=comprobantes_ajenos[0].id,
            lote_id=lote_ajeno.id,
        )
        grupo_comprobante_ajeno = LoteComprobanteGrupo(
            comprobante_ref="GRUPO-COMPROBANTE-AJENO",
            orden=1,
            estado="autorizado",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            comprobante_id=comprobantes_ajenos[1].id,
            lote_id=lote_propio.id,
        )
        grupo_comprobante_numero_incorrecto = LoteComprobanteGrupo(
            comprobante_ref="GRUPO-NUMERO-INCORRECTO",
            orden=2,
            estado="autorizado",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            comprobante_id=comprobante_grupo_numero_incorrecto.id,
            lote_id=lote_propio.id,
        )
        grupo_comprobante_punto_incorrecto = LoteComprobanteGrupo(
            comprobante_ref="GRUPO-PUNTO-INCORRECTO",
            orden=3,
            estado="autorizado",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            comprobante_id=comprobante_grupo_punto_incorrecto.id,
            lote_id=lote_propio.id,
        )
        grupo_comprobante_tipo_incorrecto = LoteComprobanteGrupo(
            comprobante_ref="GRUPO-TIPO-INCORRECTO",
            orden=4,
            estado="autorizado",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            comprobante_id=comprobante_grupo_tipo_incorrecto.id,
            lote_id=lote_propio.id,
        )
        grupo_comprobante_sin_numero_planificado = LoteComprobanteGrupo(
            comprobante_ref="GRUPO-SIN-NUMERO-PLANIFICADO",
            orden=5,
            estado="autorizado",
            tipo_comprobante=6,
            punto_venta_numero=7,
            total_estimado=Decimal("121.00"),
            mensajes_json=[FIRMA_GLOBAL_10005],
            cae=CAE_SINTETICO_NO_REAL,
            comprobante_id=comprobante_grupo_sin_numero_planificado.id,
            lote_id=lote_propio.id,
        )
        session.add_all(
            [
                grupo_lote_ajeno,
                grupo_comprobante_ajeno,
                grupo_comprobante_numero_incorrecto,
                grupo_comprobante_punto_incorrecto,
                grupo_comprobante_tipo_incorrecto,
                grupo_comprobante_sin_numero_planificado,
            ]
        )
        await session.flush()

        session.add_all(
            [
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=7,
                    numero_planificado=101,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("121.00"),
                    payload_hash="1" * 64,
                    huella_logica="2" * 64,
                    estado="requiere_reconciliacion",
                    categoria_error="arca_batch_sin_respuesta",
                    empresa_id=empresa_propia.id,
                    punto_venta_id=punto_propio.id,
                    lote_id=lote_ajeno.id,
                    grupo_id=grupo_lote_ajeno.id,
                ),
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=7,
                    numero_planificado=102,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("121.00"),
                    payload_hash="3" * 64,
                    huella_logica="4" * 64,
                    estado="requiere_reconciliacion",
                    categoria_error="arca_batch_sin_respuesta",
                    empresa_id=empresa_propia.id,
                    punto_venta_id=punto_propio.id,
                    lote_id=lote_propio.id,
                    grupo_id=grupo_comprobante_ajeno.id,
                ),
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=7,
                    numero_planificado=103,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("121.00"),
                    payload_hash="5" * 64,
                    huella_logica="6" * 64,
                    estado="requiere_reconciliacion",
                    categoria_error="arca_batch_sin_respuesta",
                    empresa_id=empresa_propia.id,
                    punto_venta_id=punto_propio.id,
                    lote_id=lote_propio.id,
                    grupo_id=grupo_comprobante_numero_incorrecto.id,
                ),
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=7,
                    numero_planificado=104,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("121.00"),
                    payload_hash="7" * 64,
                    huella_logica="8" * 64,
                    estado="requiere_reconciliacion",
                    categoria_error="arca_batch_sin_respuesta",
                    empresa_id=empresa_propia.id,
                    punto_venta_id=punto_propio.id,
                    lote_id=lote_propio.id,
                    grupo_id=grupo_comprobante_punto_incorrecto.id,
                ),
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=7,
                    numero_planificado=105,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("121.00"),
                    payload_hash="9" * 64,
                    huella_logica="a" * 64,
                    estado="requiere_reconciliacion",
                    categoria_error="arca_batch_sin_respuesta",
                    empresa_id=empresa_propia.id,
                    punto_venta_id=punto_propio.id,
                    lote_id=lote_propio.id,
                    grupo_id=grupo_comprobante_tipo_incorrecto.id,
                ),
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=7,
                    numero_planificado=None,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("121.00"),
                    payload_hash="b" * 64,
                    huella_logica="c" * 64,
                    estado="requiere_reconciliacion",
                    categoria_error="arca_batch_sin_respuesta",
                    empresa_id=empresa_propia.id,
                    punto_venta_id=punto_propio.id,
                    lote_id=lote_propio.id,
                    grupo_id=grupo_comprobante_sin_numero_planificado.id,
                ),
            ]
        )
        await session.commit()
        return int(empresa_propia.id)


async def _sembrar_referencias_comprobante_directo(
    engine: AsyncEngine,
) -> tuple[int, dict[str, int], tuple[str, ...]]:
    """Crea referencias directas válidas y corruptas sin datos fiscales reales."""
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        empresa_propia = Empresa(
            razon_social="Emisor directo propio sintético",
            cuit="20444444445",
            condicion_iva="RI",
            domicilio="Calle directa 400",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        empresa_ajena = Empresa(
            razon_social="Emisor directo ajeno sintético",
            cuit="20555555556",
            condicion_iva="RI",
            domicilio="Calle directa 500",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        punto_propio = PuntoVenta(
            numero=7,
            nombre="Punto directo propio sintético",
            sistema="Web Services",
            es_webservice=True,
            bloqueado=False,
            activo=True,
            empresa=empresa_propia,
        )
        punto_ajeno = PuntoVenta(
            numero=7,
            nombre="Punto directo ajeno sintético",
            sistema="Web Services",
            es_webservice=True,
            bloqueado=False,
            activo=True,
            empresa=empresa_ajena,
        )
        session.add_all([empresa_propia, empresa_ajena, punto_propio, punto_ajeno])
        await session.flush()

        caes_sinteticos = (
            "77777777777201",
            "77777777777999",
            "77777777777204",
            "77777777777205",
            "77777777777206",
        )
        comprobante_ajeno = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=201,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae=caes_sinteticos[0],
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_ajena.id,
            punto_venta_id=punto_propio.id,
        )
        comprobante_numero_incorrecto = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=999,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae=caes_sinteticos[1],
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_propio.id,
        )
        comprobante_valido = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=204,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae=caes_sinteticos[2],
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_propio.id,
        )
        comprobante_punto_incorrecto = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=205,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae=caes_sinteticos[3],
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_ajeno.id,
        )
        comprobante_tipo_incorrecto = Comprobante(
            tipo_comprobante=11,
            concepto=1,
            numero=206,
            fecha_emision=date(2026, 8, 8),
            subtotal=Decimal("100.00"),
            descuento=Decimal("0"),
            iva_21=Decimal("21.00"),
            iva_10_5=Decimal("0"),
            iva_27=Decimal("0"),
            otros_impuestos=Decimal("0"),
            total=Decimal("121.00"),
            cae=caes_sinteticos[4],
            cae_vencimiento=date(2026, 8, 18),
            estado="autorizado",
            empresa_id=empresa_propia.id,
            punto_venta_id=punto_propio.id,
        )
        session.add_all(
            [
                comprobante_ajeno,
                comprobante_numero_incorrecto,
                comprobante_valido,
                comprobante_punto_incorrecto,
                comprobante_tipo_incorrecto,
            ]
        )
        await session.flush()

        intentos = {
            "emisor_ajeno": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=201,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="7" * 64,
                huella_logica="8" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=comprobante_ajeno.id,
            ),
            "huerfano": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=202,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="9" * 64,
                huella_logica="a" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=999_999,
            ),
            "numero_incorrecto": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=203,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="b" * 64,
                huella_logica="c" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=comprobante_numero_incorrecto.id,
            ),
            "valido": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=204,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="d" * 64,
                huella_logica="e" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=comprobante_valido.id,
            ),
            "sin_numero_planificado": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=None,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="f" * 64,
                huella_logica="0" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=comprobante_valido.id,
            ),
            "punto_incorrecto": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=205,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="1" * 64,
                huella_logica="2" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=comprobante_punto_incorrecto.id,
            ),
            "tipo_incorrecto": IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=7,
                numero_planificado=206,
                fecha_emision=date(2026, 8, 8),
                total=Decimal("121.00"),
                payload_hash="3" * 64,
                huella_logica="4" * 64,
                estado="requiere_reconciliacion",
                categoria_error="arca_respuesta_incierta",
                empresa_id=empresa_propia.id,
                punto_venta_id=punto_propio.id,
                comprobante_id=comprobante_tipo_incorrecto.id,
            ),
        }
        session.add_all(intentos.values())
        await session.flush()
        ids_intentos = {nombre: int(intento.id) for nombre, intento in intentos.items()}
        await session.commit()
        return int(empresa_propia.id), ids_intentos, caes_sinteticos


async def _sembrar_volumen(
    engine: AsyncEngine,
    cantidad: int,
) -> int:
    """Crea un volumen sintético acotado para probar el máximo duro."""
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        empresa = Empresa(
            razon_social="Emisor de volumen sintético",
            cuit="20333333334",
            condicion_iva="RI",
            domicilio="Calle volumen 300",
            localidad="Buenos Aires",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        punto = PuntoVenta(
            numero=9,
            nombre="Punto de volumen sintético",
            sistema="Web Services",
            es_webservice=True,
            bloqueado=False,
            activo=True,
            empresa=empresa,
        )
        session.add_all([empresa, punto])
        await session.flush()
        session.add_all(
            [
                IntentoEmisionFiscal(
                    tipo_comprobante=6,
                    punto_venta_numero=9,
                    numero_planificado=None,
                    fecha_emision=date(2026, 8, 8),
                    total=Decimal("1.00"),
                    payload_hash=f"{indice:064x}",
                    huella_logica=f"{indice + cantidad:064x}",
                    estado="requiere_reconciliacion",
                    categoria_error="arca_respuesta_incierta",
                    empresa_id=empresa.id,
                    punto_venta_id=punto.id,
                )
                for indice in range(cantidad)
            ]
        )
        await session.commit()
        return int(empresa.id)


async def _contar_intentos(engine: AsyncEngine) -> int:
    """Cuenta intentos para demostrar que el inventario no muta la base."""
    async with engine.connect() as connection:
        return int(
            (
                await connection.execute(
                    select(func.count()).select_from(IntentoEmisionFiscal)
                )
            ).scalar_one()
        )


@pytest.mark.asyncio
async def test_inventario_es_solo_lectura_sanitizado_y_no_terminal(
    tmp_path: Path,
) -> None:
    """Deduplica por intento y no convierte una firma textual en saneamiento."""
    engine = await _crear_engine_sintetico(tmp_path)
    empresa_id = await _sembrar_candidatos(engine)
    antes = await _contar_intentos(engine)
    sentencias: list[str] = []

    def registrar_sql(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        sentencias.append(" ".join(statement.strip().upper().split()))

    event.listen(engine.sync_engine, "before_cursor_execute", registrar_sql)
    try:
        resultado = await inventariar_legacy_pf19(
            engine,
            FiltrosInventarioLegacyPF19(
                ambiente_runtime="produccion",
                empresa_id=empresa_id,
            ),
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", registrar_sql)

    despues = await _contar_intentos(engine)
    async with engine.connect() as connection:
        query_only_restaurado = int(
            (await connection.execute(text("PRAGMA query_only"))).scalar_one()
        )
    await engine.dispose()

    assert antes == despues == 5
    assert query_only_restaurado == 0
    assert resultado["modo"] == "solo_lectura"
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", resultado["generado_el"])
    assert resultado["ambiente_contexto_actual"] == "produccion"
    assert "ambiente_runtime" not in resultado
    assert resultado["ambiente_historico"] == "indeterminado"
    assert resultado["aislamiento_ambiente_historico_demostrable"] is False
    assert resultado["solicitudes_fecae_reconstruibles"] is False
    assert resultado["cantidad_registros"] == 5
    assert resultado["conteos_por_clasificacion"] == {
        "candidato_10005_no_confirmado": 1,
        "incertidumbre_sin_codigo_preservado": 1,
        "marcador_inconsistente_con_estado": 1,
        "preautorizacion_con_cae_o_comprobante": 1,
        "referencia_fuera_de_alcance": 1,
    }
    assert {
        registro["evidencia_codigo_10005"] for registro in resultado["registros"]
    } == {"ausente", "firma_global_legacy"}
    assert all(
        registro["tiene_cae"] is False and registro["tiene_comprobante"] is False
        for registro in resultado["registros"]
    )
    assert sum(registro["grupo_tiene_cae"] for registro in resultado["registros"]) == 1
    registro_fuera_de_alcance = next(
        registro
        for registro in resultado["registros"]
        if registro["clasificacion_inventario"] == "referencia_fuera_de_alcance"
    )
    assert registro_fuera_de_alcance["referencias"]["operacion"] == ("fuera_de_alcance")
    assert registro_fuera_de_alcance["evidencia_codigo_10005"] == "ausente"
    serializado = json.dumps(resultado, ensure_ascii=False)
    assert FIRMA_GLOBAL_10005 not in serializado
    assert "Empresa sintética" not in serializado
    assert "20123456789" not in serializado
    assert all(sentencia.startswith(("SELECT ", "PRAGMA ")) for sentencia in sentencias)


@pytest.mark.asyncio
async def test_sqlite_rechaza_dml_durante_inventario(tmp_path: Path) -> None:
    """La garantía query_only bloquea DML aunque el código intentara desviarse."""
    engine = await _crear_engine_sintetico(tmp_path)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        await activar_transaccion_solo_lectura(connection)
        with pytest.raises(DBAPIError):
            await connection.execute(
                text("UPDATE puntos_venta SET activo = 0 WHERE 1 = 0")
            )
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_inventario_restaura_query_only_previo_aun_si_falla(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La salida excepcional no debe reducir una protección previa del engine."""
    engine = await _crear_engine_sintetico(tmp_path)
    empresa_id = await _sembrar_candidatos(engine)
    sentencias: list[str] = []

    def activar_query_only_inicial(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only = ON")
        cursor.close()

    def registrar_sql(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        sentencias.append(" ".join(statement.strip().upper().split()))

    event.listen(engine.sync_engine, "connect", activar_query_only_inicial)
    event.listen(engine.sync_engine, "before_cursor_execute", registrar_sql)

    def fallar_sanitizacion(_row):
        raise RuntimeError("fallo sintético")

    monkeypatch.setattr(
        inventario_module,
        "_sanitizar_registro",
        fallar_sanitizacion,
    )
    try:
        with pytest.raises(RuntimeError, match="fallo sintético"):
            await inventariar_legacy_pf19(
                engine,
                FiltrosInventarioLegacyPF19(
                    ambiente_runtime="produccion",
                    empresa_id=empresa_id,
                ),
            )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", registrar_sql)
        event.remove(engine.sync_engine, "connect", activar_query_only_inicial)
        await engine.dispose()

    assert "PRAGMA QUERY_ONLY = 1" in sentencias


def test_filtros_inventario_rechazan_campos_desconocidos() -> None:
    """El contrato administrativo no acepta SQL ni opciones no declaradas."""
    with pytest.raises(PydanticValidationError, match="extra_forbidden"):
        FiltrosInventarioLegacyPF19.model_validate(
            {
                "ambiente_runtime": "produccion",
                "empresa_id": 1,
                "consulta_sql": "SELECT 1",
            }
        )


def test_filtros_inventario_exigen_empresa() -> None:
    """El inventario no admite barrer silenciosamente todos los emisores."""
    with pytest.raises(PydanticValidationError, match="missing"):
        FiltrosInventarioLegacyPF19.model_validate({"ambiente_runtime": "produccion"})


def test_cli_inventario_exige_empresa() -> None:
    """La CLI falla cerrado si no recibe el emisor del incidente."""
    with pytest.raises(SystemExit) as exc_info:
        construir_parser().parse_args([])

    assert exc_info.value.code == 2


def test_cli_inventario_no_expone_error_interno_ni_promete_logs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Un fallo inesperado informa aborto sin traceback ni evidencia privada."""

    async def fallar_sin_exponer(_args) -> dict:
        raise RuntimeError("detalle fiscal sintético que no debe exponerse")

    monkeypatch.setattr(pf19_cli, "ejecutar_y_disponer", fallar_sin_exponer)

    codigo = pf19_cli.main(["--empresa-id", "1"])
    salida = capsys.readouterr()

    assert codigo == 2
    assert salida.out == ""
    assert salida.err == (
        "Inventario PF-19 abortado por un error interno; no se generó salida.\n"
    )
    assert "detalle fiscal sintético" not in salida.err
    assert "logs" not in salida.err


def test_consulta_inventario_aplica_maximo_mas_uno() -> None:
    """La consulta limita la materialización para detectar exceso sin truncar."""
    consulta = construir_consulta_inventario(
        FiltrosInventarioLegacyPF19(
            ambiente_runtime="produccion",
            empresa_id=1,
        )
    )
    sql = str(consulta.compile(compile_kwargs={"literal_binds": True})).upper()

    assert f"LIMIT {MAX_REGISTROS_INVENTARIO_PF19 + 1}" in sql


@pytest.mark.parametrize("valor", ["1", 1.0])
def test_filtros_inventario_rechazan_ids_coercionados(valor: object) -> None:
    """Los filtros programáticos aceptan solo enteros explícitos."""
    with pytest.raises(PydanticValidationError, match="int_type"):
        FiltrosInventarioLegacyPF19.model_validate(
            {
                "ambiente_runtime": "produccion",
                "empresa_id": valor,
            }
        )


def test_referencia_legacy_ausente_se_clasifica_como_huerfana() -> None:
    """Una FK sin fila actual nunca se trata como relación válida."""
    assert _clasificar_referencia(10, None, False) == "huerfana"


def test_referencia_huerfana_prevalece_sobre_cae_relacionado() -> None:
    """Una relación corrupta nunca se reclasifica usando evidencia fiscal."""
    fila = {
        "tiene_cae": False,
        "tiene_comprobante": False,
        "intento_estado": "requiere_reconciliacion",
    }

    assert (
        _clasificar_registro(
            fila,
            "firma_global_legacy",
            referencias={"grupo_comprobante": "huerfana"},
            grupo_tiene_cae=True,
            grupo_tiene_comprobante=True,
        )
        == "referencia_huerfana"
    )


@pytest.mark.asyncio
async def test_inventario_no_consume_senales_cruzadas_entre_emisores(
    tmp_path: Path,
) -> None:
    """Cada dimensión grupal inválida prevalece y no aporta 10005 ni CAE."""
    engine = await _crear_engine_sintetico(tmp_path)
    empresa_id = await _sembrar_corrupcion_cruzada(engine)
    try:
        resultado = await inventariar_legacy_pf19(
            engine,
            FiltrosInventarioLegacyPF19(
                ambiente_runtime="produccion",
                empresa_id=empresa_id,
            ),
        )
    finally:
        await engine.dispose()

    assert resultado["cantidad_registros"] == 6
    assert resultado["conteos_por_clasificacion"] == {"referencia_fuera_de_alcance": 6}
    assert all(
        registro["evidencia_codigo_10005"] == "ausente"
        and registro["grupo_estado"] is None
        and registro["grupo_tiene_cae"] is False
        and registro["grupo_tiene_comprobante"] is False
        for registro in resultado["registros"]
    )
    referencias = [registro["referencias"] for registro in resultado["registros"]]
    assert any(
        referencia["lote"] == "fuera_de_alcance"
        and referencia["grupo"] == "fuera_de_alcance"
        and referencia["grupo_comprobante"] == "no_evaluable"
        for referencia in referencias
    )
    assert any(
        referencia["lote"] == "valida"
        and referencia["grupo"] == "valida"
        and referencia["grupo_comprobante"] == "fuera_de_alcance"
        for referencia in referencias
    )
    assert (
        sum(
            referencia["lote"] == "valida"
            and referencia["grupo"] == "valida"
            and referencia["grupo_comprobante"] == "fuera_de_alcance"
            for referencia in referencias
        )
        == 5
    )
    assert all(
        referencia["intento_comprobante"] == "no_aplica" for referencia in referencias
    )
    serializado = json.dumps(resultado, ensure_ascii=False)
    assert FIRMA_GLOBAL_10005 not in serializado
    assert CAE_SINTETICO_NO_REAL not in serializado
    assert all(
        cae not in serializado
        for cae in (
            "88888888888999",
            "88888888888104",
            "88888888888105",
            "88888888888106",
        )
    )


@pytest.mark.asyncio
async def test_inventario_valida_comprobante_directo_antes_de_usarlo_como_evidencia(
    tmp_path: Path,
) -> None:
    """Cada dimensión directa inválida falla cerrado de forma independiente."""
    engine = await _crear_engine_sintetico(
        tmp_path,
        habilitar_claves_foraneas=False,
    )
    (
        empresa_id,
        ids_intentos,
        caes_sinteticos,
    ) = await _sembrar_referencias_comprobante_directo(engine)
    try:
        resultado = await inventariar_legacy_pf19(
            engine,
            FiltrosInventarioLegacyPF19(
                ambiente_runtime="produccion",
                empresa_id=empresa_id,
            ),
        )
    finally:
        await engine.dispose()

    registros = {
        registro["intento_id"]: registro for registro in resultado["registros"]
    }
    registro_ajeno = registros[ids_intentos["emisor_ajeno"]]
    registro_huerfano = registros[ids_intentos["huerfano"]]
    registro_numero_incorrecto = registros[ids_intentos["numero_incorrecto"]]
    registro_valido = registros[ids_intentos["valido"]]
    registro_sin_numero = registros[ids_intentos["sin_numero_planificado"]]
    registro_punto_incorrecto = registros[ids_intentos["punto_incorrecto"]]
    registro_tipo_incorrecto = registros[ids_intentos["tipo_incorrecto"]]

    assert resultado["conteos_por_clasificacion"] == {
        "preautorizacion_con_cae_o_comprobante": 1,
        "referencia_fuera_de_alcance": 5,
        "referencia_huerfana": 1,
    }
    assert registro_ajeno["referencias"]["intento_comprobante"] == ("fuera_de_alcance")
    assert registro_huerfano["referencias"]["intento_comprobante"] == "huerfana"
    assert registro_numero_incorrecto["referencias"]["intento_comprobante"] == (
        "fuera_de_alcance"
    )
    assert registro_sin_numero["referencias"]["intento_comprobante"] == (
        "fuera_de_alcance"
    )
    assert registro_punto_incorrecto["referencias"]["intento_comprobante"] == (
        "fuera_de_alcance"
    )
    assert registro_tipo_incorrecto["referencias"]["intento_comprobante"] == (
        "fuera_de_alcance"
    )
    for registro_invalido in (
        registro_ajeno,
        registro_huerfano,
        registro_numero_incorrecto,
        registro_sin_numero,
        registro_punto_incorrecto,
        registro_tipo_incorrecto,
    ):
        assert registro_invalido["tiene_comprobante"] is False
        assert registro_invalido["evidencia_codigo_10005"] == "ausente"
        assert registro_invalido["clasificacion_inventario"].startswith("referencia_")
    assert registro_valido["referencias"]["intento_comprobante"] == "valida"
    assert registro_valido["tiene_comprobante"] is True
    assert (
        registro_valido["clasificacion_inventario"]
        == "preautorizacion_con_cae_o_comprobante"
    )
    serializado = json.dumps(resultado, ensure_ascii=False)
    assert all(cae not in serializado for cae in caes_sinteticos)


@pytest.mark.asyncio
async def test_inventario_acepta_exactamente_el_maximo(tmp_path: Path) -> None:
    """El máximo duro completo se devuelve; solo máximo más uno aborta."""
    engine = await _crear_engine_sintetico(tmp_path)
    cantidad = MAX_REGISTROS_INVENTARIO_PF19
    empresa_id = await _sembrar_volumen(engine, cantidad)
    try:
        resultado = await inventariar_legacy_pf19(
            engine,
            FiltrosInventarioLegacyPF19(
                ambiente_runtime="produccion",
                empresa_id=empresa_id,
            ),
        )
        assert await _contar_intentos(engine) == cantidad
    finally:
        await engine.dispose()

    assert resultado["cantidad_registros"] == cantidad
    assert len(resultado["registros"]) == cantidad
    assert resultado["conteos_por_clasificacion"] == {
        "incertidumbre_sin_codigo_preservado": cantidad
    }


@pytest.mark.asyncio
async def test_inventario_aborta_si_supera_maximo_sin_truncar(
    tmp_path: Path,
) -> None:
    """El máximo más uno produce aborto funcional y ninguna salida parcial."""
    engine = await _crear_engine_sintetico(tmp_path)
    cantidad = MAX_REGISTROS_INVENTARIO_PF19 + 1
    empresa_id = await _sembrar_volumen(engine, cantidad)
    try:
        with pytest.raises(
            InventarioLegacyPF19Error,
            match=f"máximo de {MAX_REGISTROS_INVENTARIO_PF19} registros",
        ):
            await inventariar_legacy_pf19(
                engine,
                FiltrosInventarioLegacyPF19(
                    ambiente_runtime="produccion",
                    empresa_id=empresa_id,
                ),
            )
        assert await _contar_intentos(engine) == cantidad
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("fila", "clasificacion"),
    [
        (
            {
                "tiene_cae": True,
                "tiene_comprobante": False,
                "intento_estado": "requiere_reconciliacion",
            },
            "preautorizacion_con_cae_o_comprobante",
        ),
        (
            {
                "tiene_cae": False,
                "tiene_comprobante": True,
                "intento_estado": "requiere_reconciliacion",
            },
            "preautorizacion_con_cae_o_comprobante",
        ),
    ],
)
def test_inventario_separa_preautorizacion_con_evidencia_fiscal(
    fila: dict[str, object],
    clasificacion: str,
) -> None:
    """CAE o comprobante contradicen el candidato y nunca se corrigen en lectura."""
    assert _clasificar_registro(fila, "firma_global_legacy") == clasificacion
