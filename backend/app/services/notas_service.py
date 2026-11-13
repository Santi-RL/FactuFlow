"""Preparación de notas individuales; no reserva números ni solicita CAE."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.arca.exceptions import ArcaServiceError
from app.core.condicion_iva_receptor import CONDICIONES_IVA_IDS
from app.core.comprobante_totales import preparar_importes
from app.core.documento_receptor import normalizar_documento
from app.models.comprobante import Comprobante
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.lecturas_historicas_service import cargar_lecturas_historicas

TIPOS_NOTA = {2: 1, 3: 1, 7: 6, 8: 6, 12: 11, 13: 11}


class NotasService:
    def __init__(self, db):
        self.db = db

    async def original(self, empresa_id: int, tipo: int, punto: int, numero: int):
        if (
            tipo not in {1, 6, 11}
            or not 1 <= punto <= 99999
            or not 1 <= numero <= 99999999
        ):
            raise ValidationError(
                "Indicá una factura A, B o C, su punto de venta y número válidos."
            )
        factura = (
            await self.db.execute(
                select(Comprobante)
                .join(PuntoVenta)
                .options(
                    selectinload(Comprobante.items),
                    selectinload(Comprobante.punto_venta),
                    selectinload(Comprobante.empresa),
                )
                .where(
                    Comprobante.empresa_id == empresa_id,
                    Comprobante.tipo_comprobante == tipo,
                    Comprobante.numero == numero,
                    PuntoVenta.numero == punto,
                )
            )
        ).scalar_one_or_none()
        servicio = FacturacionService(self.db)
        empresa = await servicio._obtener_empresa(empresa_id)
        if empresa is None:
            raise ValidationError("Emisor no encontrado.")
        if factura is not None:
            if factura.estado != "autorizado" or not factura.cae:
                raise ValidationError("La factura original no está autorizada.")
            lectura = (await cargar_lecturas_historicas(self.db, [factura]))[factura.id]
            if (
                lectura.cobertura == "no_verificable"
                or lectura.punto_venta_numero != punto
                or (lectura.emisor.cuit or "").replace("-", "")
                != empresa.cuit.replace("-", "")
            ):
                raise ValidationError(
                    "No se pudieron verificar los datos originales de la factura."
                )
            receptor = dict(
                tipo_documento=factura.receptor_tipo_documento,
                numero_documento=factura.receptor_numero_documento,
                razon_social=factura.receptor_razon_social,
                condicion_iva=factura.receptor_condicion_iva,
                domicilio=factura.receptor_domicilio,
            )
            if any(
                receptor[k] is None
                for k in (
                    "tipo_documento",
                    "numero_documento",
                    "razon_social",
                    "condicion_iva",
                )
            ):
                raise ValidationError(
                    "La factura no conserva datos suficientes del receptor."
                )
            items = [
                dict(
                    codigo=i.codigo,
                    descripcion=i.descripcion,
                    cantidad=i.cantidad,
                    unidad=i.unidad,
                    precio_unitario=i.precio_unitario,
                    descuento_porcentaje=i.descuento_porcentaje,
                    iva_porcentaje=i.iva_porcentaje,
                    orden=i.orden,
                )
                for i in sorted(factura.items, key=lambda i: i.orden)
            ]
            resultado = dict(
                origen="factuflow",
                fecha=factura.fecha_emision,
                concepto=factura.concepto,
                moneda=factura.moneda,
                cotizacion=factura.cotizacion,
                total=factura.total,
                receptor=receptor,
                items=items,
                fecha_servicio_desde=factura.fecha_servicio_desde,
                fecha_servicio_hasta=factura.fecha_servicio_hasta,
                fecha_vto_pago=factura.fecha_vto_pago,
            )
        else:
            certificado = await servicio._obtener_certificado_activo(empresa_id)
            cliente = await servicio._obtener_cliente_wsfe(empresa, certificado)
            try:
                consulta = await cliente.fe_comp_consultar(
                    punto_venta=punto, tipo_cbte=tipo, numero=numero
                )
            except ArcaServiceError as exc:
                raise ValidationError(
                    "No se pudo consultar la factura en ARCA. Revisá sus datos y volvé a consultar."
                ) from exc
            if (
                consulta.resultado != "A"
                or not consulta.cae
                or not consulta.datos_basicos_completos
                or consulta.cuit_emisor != empresa.cuit.replace("-", "")
                or (consulta.tipo_cbte, consulta.punto_venta, consulta.numero)
                != (tipo, punto, numero)
                or consulta.concepto not in {1, 2, 3}
            ):
                raise ValidationError(
                    "ARCA no devolvió una factura autorizada con datos suficientes."
                )
            if any(
                v != 0
                for v in (consulta.imp_trib, consulta.imp_op_ex, consulta.imp_tot_conc)
            ):
                raise ValidationError(
                    "El original contiene tributos, importes exentos o no gravados que este formulario todavía no admite."
                )
            if consulta.adicionales_presentes:
                raise ValidationError(
                    "La factura contiene datos adicionales que este formulario todavía no admite."
                )
            try:
                fecha = date.fromisoformat(consulta.fecha_cbte)
            except ValueError:
                fecha = date(
                    int(consulta.fecha_cbte[:4]),
                    int(consulta.fecha_cbte[4:6]),
                    int(consulta.fecha_cbte[6:]),
                )
            items = []
            if tipo == 11:
                items = [self._item(consulta.imp_total, Decimal("0"))]
            else:
                tasas = {
                    3: Decimal("0"),
                    4: Decimal("10.5"),
                    5: Decimal("21"),
                    6: Decimal("27"),
                }
                for iva in consulta.iva or []:
                    if iva.id not in tasas:
                        raise ValidationError(
                            "La factura tiene una alícuota que este formulario todavía no admite."
                        )
                    items.append(self._item(iva.base_imp, tasas[iva.id]))
                    if iva.importe != (iva.base_imp * tasas[iva.id] / 100).quantize(
                        Decimal("0.01")
                    ):
                        raise ValidationError(
                            "El IVA del original no puede representarse fielmente en este formulario."
                        )
            resultado = dict(
                origen="arca",
                fecha=fecha,
                concepto=consulta.concepto,
                moneda=consulta.moneda_id,
                cotizacion=consulta.moneda_cotiz,
                total=consulta.imp_total,
                items=items,
                receptor=dict(
                    tipo_documento=consulta.tipo_doc,
                    numero_documento=str(consulta.nro_doc),
                    razon_social="",
                    condicion_iva=next(
                        (
                            k
                            for k, v in CONDICIONES_IVA_IDS.items()
                            if v == consulta.condicion_iva_receptor_id
                        ),
                        "",
                    ),
                    domicilio=None,
                ),
                fecha_servicio_desde=self._fecha(consulta.fecha_serv_desde),
                fecha_servicio_hasta=self._fecha(consulta.fecha_serv_hasta),
                fecha_vto_pago=self._fecha(consulta.fecha_vto_pago),
            )
        if resultado["moneda"] != "PES" or resultado["cotizacion"] != Decimal("1"):
            raise ValidationError(
                "Este formulario admite notas en pesos. El original está expresado en otra moneda."
            )
        try:
            importes = preparar_importes(
                [
                    ItemComprobanteCreate(
                        **{**i, "descripcion": i["descripcion"] or "Ajuste"}
                    )
                    for i in resultado["items"]
                ]
            )
        except ValueError as exc:
            raise ValidationError(
                "El detalle del original no puede representarse fielmente en este formulario."
            ) from exc
        if importes["total"] != resultado["total"]:
            raise ValidationError(
                "El detalle disponible no coincide con el importe original. No se preparó la nota."
            )
        if factura is not None and (
            factura.otros_impuestos != 0
            or any(
                importes[campo] != getattr(factura, campo)
                for campo in ("subtotal", "iva_21", "iva_10_5", "iva_27")
            )
        ):
            raise ValidationError(
                "El desglose fiscal del original no puede representarse fielmente en este formulario."
            )
        if factura is None and (
            importes["subtotal"] != consulta.imp_neto
            or sum(importes[k] for k in ("iva_21", "iva_10_5", "iva_27"))
            != consulta.imp_iva
        ):
            raise ValidationError(
                "No se pudo representar fielmente el desglose fiscal de la factura."
            )
        return {
            **resultado,
            "importes": importes,
            "asociado": dict(
                tipo_comprobante=tipo,
                punto_venta=punto,
                numero=numero,
                fecha=resultado["fecha"],
                cuit=empresa.cuit.replace("-", ""),
            ),
        }

    @staticmethod
    def _fecha(valor):
        if not valor:
            return None
        if len(valor) == 8:
            return date(int(valor[:4]), int(valor[4:6]), int(valor[6:]))
        return date.fromisoformat(valor)

    @staticmethod
    def _item(importe, tasa):
        # WSFE no devuelve el detalle comercial: el usuario completa la descripción.
        return dict(
            descripcion="",
            cantidad=Decimal("1"),
            unidad="unidades",
            precio_unitario=importe,
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=tasa,
            orden=0,
        )

    async def validar(self, request):
        # Los consumidores técnicos anteriores no declaraban un alcance.
        # Conservan su contrato y las validaciones ARCA existentes; la nueva
        # preparación individual siempre declara total, parcial o ajuste.
        if request.tipo_comprobante not in TIPOS_NOTA or request.alcance_nota is None:
            return
        if len(request.comprobantes_asociados) != 1:
            raise ValidationError("Seleccioná la factura que se ajusta con esta nota.")
        asociado = request.comprobantes_asociados[0]
        if asociado.tipo_comprobante != TIPOS_NOTA[request.tipo_comprobante]:
            raise ValidationError(
                "La nota debe ser de la misma clase que la factura original."
            )
        original = await self.original(
            request.empresa_id,
            asociado.tipo_comprobante,
            asociado.punto_venta,
            asociado.numero,
        )
        if asociado.model_dump() != original["asociado"]:
            raise ValidationError(
                "La referencia de la factura cambió. Volvé a seleccionar el original."
            )
        receptor = original["receptor"]
        if request.tipo_documento != receptor["tipo_documento"] or normalizar_documento(
            request.numero_documento, request.tipo_documento
        ) != normalizar_documento(
            receptor["numero_documento"], receptor["tipo_documento"]
        ):
            raise ValidationError(
                "La nota debe emitirse al mismo receptor que la factura original."
            )
        if (
            request.moneda != original["moneda"]
            or request.cotizacion != original["cotizacion"]
        ):
            raise ValidationError(
                "La moneda y cotización deben coincidir con la factura original."
            )
        if request.fecha_emision < original["fecha"]:
            raise ValidationError(
                "La fecha de la nota no puede ser anterior a la factura original."
            )
        importes = FacturacionService(self.db).preparar_importes(request.items)
        if request.tipo_comprobante in {3, 8, 13}:
            if request.alcance_nota not in {"total", "parcial"}:
                raise ValidationError("Indicá si el crédito es total o parcial.")
            if request.alcance_nota == "total" and any(
                importes[k] != original["importes"][k]
                for k in importes
                if k != "subtotales_items"
            ):
                raise ValidationError(
                    "Para un crédito total, los importes y el IVA deben coincidir con el original."
                )
            if (
                request.alcance_nota == "parcial"
                and importes["total"] >= original["total"]
            ):
                raise ValidationError(
                    "El crédito parcial debe ser menor al importe original; para el total elegí crédito total."
                )
            if request.alcance_nota == "parcial" and any(
                importes[campo] > original["importes"][campo]
                for campo in (
                    "base_0",
                    "base_10_5",
                    "base_21",
                    "base_27",
                    "iva_10_5",
                    "iva_21",
                    "iva_27",
                )
            ):
                raise ValidationError(
                    "Revisá los ítems del crédito parcial: sus bases e importes de IVA no pueden superar los de cada tasa del original."
                )
        elif request.alcance_nota != "ajuste":
            raise ValidationError(
                "Ingresá el ajuste que corresponde a la nota de débito."
            )
