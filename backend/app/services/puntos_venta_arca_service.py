"""Comprobación técnica durable de puntos de venta contra ARCA."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.config import ArcaAmbiente
from app.arca.utils import clean_cuit
from app.arca.wsaa import WSAAClient
from app.arca.wsfev1 import WSFEv1Client
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta
from app.services.certificados_service import requerir_material_certificado
from app.services.elegibilidad_rece_service import (
    ElegibilidadReceError,
    ElegibilidadReceService,
)


class PuntosVentaArcaService:
    """Actualiza una señal técnica sin promover acreditaciones RECE."""

    def __init__(self, db: AsyncSession, *, ahora: datetime | None = None) -> None:
        """Inicializa el servicio con un reloj UTC inyectable."""
        self.db = db
        self._ahora = ahora

    def _obtener_ahora(self) -> datetime:
        """Devuelve el instante UTC compartido por una comprobación completa."""
        return self._ahora or datetime.utcnow()

    @staticmethod
    def _ambiente() -> ArcaAmbiente:
        """Resuelve el ambiente configurado sin aceptar valores ambiguos."""
        ambiente = settings.arca_env.strip().lower()
        if ambiente == ArcaAmbiente.PRODUCCION.value:
            return ArcaAmbiente.PRODUCCION
        if ambiente == ArcaAmbiente.HOMOLOGACION.value:
            return ArcaAmbiente.HOMOLOGACION
        raise ElegibilidadReceError("El ambiente ARCA configurado no es válido.")

    async def _crear_cliente(self, empresa_id: int) -> WSFEv1Client:
        """Autentica una consulta WSFE de solo lectura para el emisor."""
        empresa = await self.db.get(Empresa, empresa_id)
        if empresa is None:
            raise ElegibilidadReceError("El emisor activo no existe.")
        certificado = (
            await self.db.execute(
                select(Certificado)
                .where(
                    Certificado.empresa_id == empresa_id,
                    Certificado.activo.is_(True),
                    Certificado.ambiente == self._ambiente().value,
                )
                .order_by(
                    Certificado.fecha_vencimiento.desc(),
                    Certificado.id.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if certificado is None:
            raise ElegibilidadReceError(
                "No hay un certificado activo para comprobar el punto con ARCA."
            )
        cert_path, key_path = requerir_material_certificado(
            certificado.archivo_crt,
            certificado.archivo_key,
        )
        ticket = await WSAAClient(self._ambiente()).login(
            cert_path=str(cert_path),
            key_path=str(key_path),
            cuit=clean_cuit(empresa.cuit),
            servicio="wsfe",
        )
        return WSFEv1Client(
            ambiente=self._ambiente(),
            ticket=ticket,
            cuit=clean_cuit(empresa.cuit),
        )

    @staticmethod
    def _normalizar_puntos_remotos(
        puntos: list[Any],
    ) -> dict[int, dict[str, str | bool | None]]:
        """Valida el conjunto completo antes de permitir cambios locales."""
        if not puntos:
            raise ElegibilidadReceError(
                "ARCA no informó puntos de venta; no se aplicaron cambios.",
                categoria="comprobacion_arca_no_disponible",
                status_code=503,
            )
        try:
            numeros = [int(punto.numero) for punto in puntos]
            bloqueos = [str(punto.bloqueado).strip().upper() for punto in puntos]
        except (AttributeError, TypeError, ValueError) as exc:
            raise ElegibilidadReceError(
                "ARCA devolvió un estado técnico inconsistente.",
                categoria="comprobacion_arca_no_disponible",
                status_code=503,
            ) from exc
        if (
            len(set(numeros)) != len(numeros)
            or any(numero < 1 or numero > 99999 for numero in numeros)
            or any(bloqueo not in {"S", "N"} for bloqueo in bloqueos)
        ):
            raise ElegibilidadReceError(
                "ARCA devolvió un estado técnico inconsistente.",
                categoria="comprobacion_arca_no_disponible",
                status_code=503,
            )
        return {
            int(punto.numero): {
                "bloqueado": str(punto.bloqueado).strip().upper() == "S",
                "fecha_baja": (
                    None
                    if not str(punto.fecha_baja or "").strip()
                    or str(punto.fecha_baja or "").strip().upper() == "NULL"
                    else str(punto.fecha_baja).strip()
                ),
                "emision_tipo": str(getattr(punto, "emision_tipo", "") or ""),
            }
            for punto in puntos
        }

    @staticmethod
    def _sistema_webservice(emision_tipo: str | None) -> str:
        """Construye una descripción técnica sin inferir membresía RECE."""
        detalle = re.sub(r"^CAE\s*-\s*", "", (emision_tipo or "").strip(), flags=re.I)
        if detalle:
            return f"Factura Electrónica - {detalle} - Web Services"
        return "Factura Electrónica - Web Services"

    async def sincronizar(
        self,
        *,
        empresa_id: int,
        actor_usuario_id: int | None,
        wsfe_client: WSFEv1Client | None = None,
    ) -> dict[str, int | datetime]:
        """Aplica un snapshot técnico completo con una única transacción."""
        try:
            cliente = wsfe_client or await self._crear_cliente(empresa_id)
            remotos = self._normalizar_puntos_remotos(
                list(await cliente.fe_param_get_ptos_venta())
            )
        except ElegibilidadReceError:
            await self.db.rollback()
            raise
        except Exception as exc:
            await self.db.rollback()
            raise ElegibilidadReceError(
                "No se pudo comprobar el estado de los puntos de venta con ARCA.",
                categoria="comprobacion_arca_no_disponible",
                status_code=503,
            ) from exc

        comprobado_en = self._obtener_ahora()
        existentes = {
            int(punto.numero): punto
            for punto in (
                await self.db.execute(
                    select(PuntoVenta).where(PuntoVenta.empresa_id == empresa_id)
                )
            )
            .scalars()
            .all()
        }
        elegibilidad = ElegibilidadReceService(self.db, ahora=comprobado_en)
        cambios: list[tuple[PuntoVenta, dict[str, object]]] = []
        nuevos = 0
        existentes_en_arca = 0
        actualizados = 0

        try:
            for numero, remoto in remotos.items():
                bloqueado = bool(remoto["bloqueado"])
                fecha_baja = remoto["fecha_baja"]
                activo = not bloqueado and not fecha_baja
                sistema = self._sistema_webservice(str(remoto["emision_tipo"]))
                punto = existentes.get(numero)
                if punto is None:
                    punto = PuntoVenta(
                        numero=numero,
                        nombre=sistema,
                        sistema=sistema,
                        es_webservice=True,
                        bloqueado=bloqueado,
                        fecha_baja=fecha_baja,
                        fuente="arca_wsfe",
                        activo=activo,
                        empresa_id=empresa_id,
                        ultima_comprobacion_arca_en=comprobado_en,
                    )
                    self.db.add(punto)
                    await elegibilidad.crear_contextos_iniciales_no_verificados(
                        punto,
                        creado_por_usuario_id=actor_usuario_id,
                        fuente="sincronizacion_wsfe",
                    )
                    nuevos += 1
                    continue

                existentes_en_arca += 1
                sistema_actual = (
                    punto.sistema
                    if punto.sistema
                    and re.search(r"web\s*services?", punto.sistema, flags=re.I)
                    else sistema
                )
                valores: dict[str, object] = {
                    "nombre": punto.nombre or sistema_actual,
                    "sistema": sistema_actual,
                    "es_webservice": True,
                    "bloqueado": bloqueado,
                    "fecha_baja": fecha_baja,
                    "fuente": punto.fuente or "arca_wsfe",
                    "activo": activo,
                    "ultima_comprobacion_arca_en": comprobado_en,
                }
                cambios_tecnicos = {
                    campo: valor
                    for campo, valor in valores.items()
                    if campo != "ultima_comprobacion_arca_en"
                }
                if any(
                    getattr(punto, campo) != valor
                    for campo, valor in cambios_tecnicos.items()
                ):
                    actualizados += 1
                cambios.append((punto, valores))

            numeros_arca = set(remotos)
            ausentes = [
                punto
                for numero, punto in existentes.items()
                if numero not in numeros_arca
            ]
            cambios.extend(
                (
                    punto,
                    {
                        "activo": False,
                        "ultima_comprobacion_arca_en": comprobado_en,
                    },
                )
                for punto in ausentes
            )
            if cambios:
                await elegibilidad.aplicar_cambios_puntos_atomicos(
                    cambios,
                    fuente="sincronizacion_wsfe",
                    actor_usuario_id=actor_usuario_id,
                )
            else:
                await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return {
            "total_arca": len(remotos),
            "nuevos": nuevos,
            "existentes": existentes_en_arca,
            "actualizados": actualizados,
            "desactivados_ausentes": len(ausentes),
            "comprobado_en": comprobado_en,
        }

    async def asegurar_comprobacion_reciente(
        self,
        *,
        empresa_id: int,
        puntos_venta_ids: list[int] | set[int],
        actor_usuario_id: int | None,
    ) -> bool:
        """Refresca una señal pendiente o de 90 días antes del borde fiscal."""
        ids = sorted({int(punto_id) for punto_id in puntos_venta_ids})
        if not ids or settings.arca_env != "produccion":
            return False
        puntos = list(
            (
                await self.db.execute(
                    select(PuntoVenta).where(
                        PuntoVenta.empresa_id == empresa_id,
                        PuntoVenta.id.in_(ids),
                    )
                )
            ).scalars()
        )
        if len(puntos) != len(ids):
            raise ElegibilidadReceError(
                "Un punto de venta no pertenece al emisor activo."
            )
        elegibilidad = ElegibilidadReceService(self.db, ahora=self._obtener_ahora())
        estados = [
            await elegibilidad.obtener_estado_visible(
                punto,
                ambiente="produccion",
            )
            for punto in puntos
        ]
        if any(estado.estado_efectivo != "verificado_rece" for estado in estados):
            return False
        if not any(
            elegibilidad.comprobacion_arca_desactualizada(punto) for punto in puntos
        ):
            return False
        await self.sincronizar(
            empresa_id=empresa_id,
            actor_usuario_id=actor_usuario_id,
        )
        return True
