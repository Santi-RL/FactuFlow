"""Cliente para el Web Service de Factura Electrónica v1 (WSFEv1) de ARCA."""

import logging
from typing import List

from zeep.exceptions import Fault, TransportError

from app.arca.config import ArcaAmbiente, ArcaConfig
from app.arca.models import (
    TicketAcceso,
    CAEResponse,
    ComprobanteRequest,
    ComprobanteResponse,
    TipoComprobante,
    TipoDocumento,
    TipoIva,
    TipoConcepto,
    TipoMoneda,
    Cotizacion,
    PuntoVenta,
    Observacion,
    ErrorArca,
)
from app.arca.exceptions import (
    ArcaServiceError,
    ArcaValidationError,
    ArcaConnectionError,
)
from app.arca.soap import create_soap_client, run_soap_call
from app.arca.utils import clean_cuit, format_importe

logger = logging.getLogger(__name__)


class WSFEv1Client:
    """
    Cliente para el Web Service de Factura Electrónica v1 (WSFEv1).

    Este servicio permite:
    - Emitir comprobantes electrónicos y obtener CAE
    - Consultar comprobantes emitidos
    - Obtener parámetros (tipos de comprobante, IVA, monedas, etc.)
    - Consultar último número de comprobante autorizado
    """

    def __init__(self, ambiente: ArcaAmbiente, ticket: TicketAcceso, cuit: str):
        """
        Inicializa el cliente WSFEv1.

        Args:
            ambiente: Ambiente de ARCA (homologacion o produccion)
            ticket: Ticket de acceso obtenido del WSAA
            cuit: CUIT de la empresa
        """
        self.config = ArcaConfig(ambiente=ambiente)
        self.ticket = ticket
        self.cuit = clean_cuit(cuit)

        # Cliente SOAP
        try:
            self.client = create_soap_client(self.config.wsfe_url)
        except Exception as e:
            raise ArcaConnectionError(f"Error al conectar con WSFEv1: {str(e)}")

    def _get_auth_dict(self) -> dict:
        """
        Obtiene el diccionario de autenticación para las llamadas SOAP.

        Returns:
            Dict con Token, Sign y Cuit
        """
        return {"Token": self.ticket.token, "Sign": self.ticket.sign, "Cuit": self.cuit}

    async def _call_soap(self, method_name: str, **kwargs: object) -> object:
        """Ejecuta un método Zeep sin bloquear el event loop."""

        method = getattr(self.client.service, method_name)
        return await run_soap_call(method, **kwargs)

    async def fe_dummy(self) -> dict:
        """
        Test de disponibilidad del servicio (FEDummy).

        Este método no requiere autenticación y sirve para verificar que
        el webservice está disponible.

        Returns:
            Dict con información del servidor

        Raises:
            ArcaConnectionError: Si hay error de conexión
            ArcaServiceError: Si hay error del servicio
        """
        try:
            response = await self._call_soap("FEDummy")

            return {
                "app_server": response.AppServer,
                "db_server": response.DbServer,
                "auth_server": response.AuthServer,
            }

        except TransportError as e:
            raise ArcaConnectionError(f"Error de conexión con WSFEv1: {str(e)}")
        except Exception as e:
            raise ArcaServiceError(f"Error en FEDummy: {str(e)}")

    async def fe_comp_ultimo_autorizado(self, punto_venta: int, tipo_cbte: int) -> int:
        """
        Obtiene el último número de comprobante autorizado.

        Args:
            punto_venta: Punto de venta
            tipo_cbte: Tipo de comprobante

        Returns:
            Último número de comprobante

        Raises:
            ArcaServiceError: Si hay error del servicio
        """
        try:
            auth = self._get_auth_dict()

            response = await self._call_soap(
                "FECompUltimoAutorizado",
                Auth=auth,
                PtoVta=punto_venta,
                CbteTipo=tipo_cbte,
            )

            # Verificar errores
            if hasattr(response, "Errors") and response.Errors:
                error = (
                    response.Errors.Err[0]
                    if isinstance(response.Errors.Err, list)
                    else response.Errors.Err
                )
                raise ArcaServiceError(
                    f"Error al obtener último comprobante: {error.Msg}",
                    codigo=str(error.Code),
                )

            return response.CbteNro

        except Fault as e:
            raise ArcaServiceError(f"Error SOAP: {e.message}")
        except ArcaServiceError:
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error inesperado: {str(e)}")

    async def fe_cae_solicitar(self, comprobante: ComprobanteRequest) -> CAEResponse:
        """
        Solicita CAE (Código de Autorización Electrónica) para un comprobante.

        Args:
            comprobante: Datos del comprobante

        Returns:
            CAEResponse con el CAE y datos del comprobante

        Raises:
            ArcaValidationError: Si hay errores de validación
            ArcaServiceError: Si hay error del servicio
        """
        try:
            resultados = await self.fe_cae_solicitar_lote(
                [comprobante],
                rechazar_detalles_no_aprobados=True,
            )
            return resultados[0]

        except Fault as e:
            raise ArcaServiceError(f"Error SOAP: {e.message}")
        except (ArcaValidationError, ArcaServiceError):
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error inesperado: {str(e)}")

    async def fe_cae_solicitar_lote(
        self,
        comprobantes: list[ComprobanteRequest],
        rechazar_detalles_no_aprobados: bool = False,
    ) -> list[CAEResponse]:
        """
        Solicita CAE para un lote homogéneo de comprobantes WSFE.

        Todos los comprobantes deben compartir punto de venta y tipo. La
        cantidad máxima debe resolverse previamente con `FECompTotXRequest`.
        """
        if not comprobantes:
            raise ArcaValidationError("El lote ARCA debe incluir comprobantes")

        punto_venta = comprobantes[0].punto_venta
        tipo_cbte = comprobantes[0].tipo_cbte
        if any(
            comprobante.punto_venta != punto_venta or comprobante.tipo_cbte != tipo_cbte
            for comprobante in comprobantes
        ):
            raise ArcaValidationError(
                "Todos los comprobantes del request ARCA deben tener el mismo "
                "punto de venta y tipo"
            )

        try:
            auth = self._get_auth_dict()
            response = await self._call_soap(
                "FECAESolicitar",
                Auth=auth,
                FeCAEReq={
                    "FeCabReq": {
                        "CantReg": len(comprobantes),
                        "PtoVta": punto_venta,
                        "CbteTipo": tipo_cbte,
                    },
                    "FeDetReq": {
                        "FECAEDetRequest": [
                            self._build_fe_det_request(comprobante)
                            for comprobante in comprobantes
                        ]
                    },
                },
            )
            return self._parse_cae_response_list(
                response,
                comprobantes,
                rechazar_detalles_no_aprobados=rechazar_detalles_no_aprobados,
            )

        except Fault as e:
            raise ArcaServiceError(f"Error SOAP: {e.message}")
        except (ArcaValidationError, ArcaServiceError):
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error inesperado: {str(e)}")

    async def fe_comp_tot_x_request(self) -> int:
        """
        Consulta la cantidad máxima de registros permitida por request WSFE.

        Returns:
            Valor `RegXReq` informado por ARCA para FECAESolicitar.
        """
        try:
            response = await self._call_soap(
                "FECompTotXRequest",
                Auth=self._get_auth_dict(),
            )

            if hasattr(response, "Errors") and response.Errors:
                error = (
                    response.Errors.Err[0]
                    if isinstance(response.Errors.Err, list)
                    else response.Errors.Err
                )
                raise ArcaServiceError(
                    f"Error al obtener RegXReq: {error.Msg}",
                    codigo=str(error.Code),
                )

            result = getattr(response, "ResultGet", response)
            reg_x_req = getattr(result, "RegXReq", None)
            if reg_x_req is None:
                raise ArcaServiceError("ARCA no devolvió RegXReq")

            return int(reg_x_req)

        except ArcaServiceError:
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error al obtener RegXReq: {str(e)}")

    def _build_fe_det_request(self, comprobante: ComprobanteRequest) -> dict:
        """Construye el detalle `FECAEDetRequest` para un comprobante."""
        fe_det = {
            "Concepto": comprobante.concepto,
            "DocTipo": comprobante.tipo_doc,
            "DocNro": comprobante.nro_doc,
            "CbteDesde": comprobante.cbte_desde,
            "CbteHasta": comprobante.cbte_hasta,
            "CbteFch": comprobante.fecha_cbte,
            "ImpTotal": format_importe(comprobante.imp_total),
            "ImpTotConc": format_importe(comprobante.imp_tot_conc),
            "ImpNeto": format_importe(comprobante.imp_neto),
            "ImpOpEx": format_importe(comprobante.imp_op_ex),
            "ImpIVA": format_importe(comprobante.imp_iva),
            "ImpTrib": format_importe(comprobante.imp_trib),
            "MonId": comprobante.moneda_id,
            "MonCotiz": comprobante.moneda_cotiz,
        }

        if comprobante.condicion_iva_receptor_id is not None:
            fe_det["CondicionIVAReceptorId"] = comprobante.condicion_iva_receptor_id

        if comprobante.fecha_serv_desde:
            fe_det["FchServDesde"] = comprobante.fecha_serv_desde
        if comprobante.fecha_serv_hasta:
            fe_det["FchServHasta"] = comprobante.fecha_serv_hasta
        if comprobante.fecha_vto_pago:
            fe_det["FchVtoPago"] = comprobante.fecha_vto_pago

        if comprobante.iva:
            fe_det["Iva"] = {
                "AlicIva": [
                    {
                        "Id": iva.id,
                        "BaseImp": format_importe(iva.base_imp),
                        "Importe": format_importe(iva.importe),
                    }
                    for iva in comprobante.iva
                ]
            }

        if comprobante.tributos:
            fe_det["Tributos"] = {
                "Tributo": [
                    {
                        "Id": trib.id,
                        "Desc": trib.descripcion,
                        "BaseImp": format_importe(trib.base_imp),
                        "Alic": trib.alic,
                        "Importe": format_importe(trib.importe),
                    }
                    for trib in comprobante.tributos
                ]
            }

        if comprobante.cbtes_asoc:
            fe_det["CbtesAsoc"] = {
                "CbteAsoc": [
                    {
                        key: value
                        for key, value in {
                            "Tipo": asociado.tipo,
                            "PtoVta": asociado.punto_venta,
                            "Nro": asociado.numero,
                            "Cuit": asociado.cuit,
                            "CbteFch": asociado.fecha_cbte,
                        }.items()
                        if value is not None
                    }
                    for asociado in comprobante.cbtes_asoc
                ]
            }

        return fe_det

    def _parse_cae_response(
        self, response, comprobante: ComprobanteRequest
    ) -> CAEResponse:
        """
        Parsea la respuesta de FECAESolicitar.

        Args:
            response: Respuesta del servicio
            comprobante: Comprobante solicitado

        Returns:
            CAEResponse

        Raises:
            ArcaValidationError: Si el comprobante fue rechazado
        """
        return self._parse_cae_response_list(
            response,
            [comprobante],
            rechazar_detalles_no_aprobados=True,
        )[0]

    def _parse_cae_response_list(
        self,
        response,
        comprobantes: list[ComprobanteRequest],
        rechazar_detalles_no_aprobados: bool,
    ) -> list[CAEResponse]:
        """Parsea una respuesta WSFE que puede contener varios detalles."""
        detalles = self._normalizar_lista(
            getattr(getattr(response, "FeDetResp", None), "FECAEDetResponse", None)
        )
        errores = self._parse_errors_response(response)

        if not detalles:
            mensajes = "; ".join(f"[{e.code}] {e.msg}" for e in errores)
            raise ArcaServiceError(
                f"ARCA no devolvió detalle de comprobantes. {mensajes}".strip()
            )

        if len(detalles) != len(comprobantes):
            raise ArcaServiceError(
                "ARCA devolvió una cantidad de detalles distinta a la solicitada"
            )

        detalles_ordenados = self._ordenar_detalles_cae_por_comprobante(
            detalles,
            comprobantes,
        )
        resultados = [
            self._parse_cae_det_response(detalle, comprobante, errores)
            for detalle, comprobante in zip(detalles_ordenados, comprobantes)
        ]

        if rechazar_detalles_no_aprobados:
            for resultado in resultados:
                if resultado.is_rechazado:
                    error_msgs = [f"[{e.code}] {e.msg}" for e in resultado.errores]
                    obs_msgs = [f"[{o.code}] {o.msg}" for o in resultado.observaciones]
                    all_msgs = error_msgs + obs_msgs
                    raise ArcaValidationError(
                        f"Comprobante rechazado: {'; '.join(all_msgs)}"
                    )

        return resultados

    def _ordenar_detalles_cae_por_comprobante(
        self,
        detalles,
        comprobantes: list[ComprobanteRequest],
    ):
        """Ordena detalles ARCA por rango fiscal y valida correspondencia exacta."""
        detalles_por_rango = {}
        for detalle in detalles:
            cbte_desde_raw = getattr(detalle, "CbteDesde", None)
            cbte_hasta_raw = getattr(detalle, "CbteHasta", None)
            if cbte_desde_raw is None:
                raise ArcaServiceError(
                    "ARCA devolvió un detalle de comprobante sin CbteDesde"
                )
            if cbte_hasta_raw is None:
                raise ArcaServiceError(
                    "ARCA devolvió un detalle de comprobante sin CbteHasta"
                )
            try:
                cbte_desde = int(cbte_desde_raw)
                cbte_hasta = int(cbte_hasta_raw)
            except (TypeError, ValueError) as exc:
                raise ArcaServiceError(
                    "ARCA devolvió un rango de comprobante inválido en un detalle: "
                    f"CbteDesde={cbte_desde_raw}, CbteHasta={cbte_hasta_raw}"
                ) from exc
            rango = (cbte_desde, cbte_hasta)
            if rango in detalles_por_rango:
                raise ArcaServiceError(
                    "ARCA devolvió un rango de comprobante duplicado en la "
                    f"respuesta: {cbte_desde}-{cbte_hasta}"
                )
            detalles_por_rango[rango] = detalle

        rangos_solicitados = [
            (int(comprobante.cbte_desde), int(comprobante.cbte_hasta))
            for comprobante in comprobantes
        ]
        solicitados_set = set(rangos_solicitados)
        recibidos_set = set(detalles_por_rango)
        if solicitados_set != recibidos_set:
            partes = []
            faltantes = sorted(solicitados_set - recibidos_set)
            extras = sorted(recibidos_set - solicitados_set)
            if faltantes:
                partes.append(f"faltantes: {faltantes}")
            if extras:
                partes.append(f"no solicitados: {extras}")
            raise ArcaServiceError(
                "ARCA devolvió detalles para números distintos o rangos distintos "
                "a los solicitados "
                f"({'; '.join(partes)})"
            )

        return [detalles_por_rango[rango] for rango in rangos_solicitados]

    def _parse_cae_det_response(
        self,
        fe_det_resp,
        comprobante: ComprobanteRequest,
        errores: list[ErrorArca],
    ) -> CAEResponse:
        """Convierte un `FECAEDetResponse` en `CAEResponse`."""
        # Extraer observaciones
        observaciones = []
        if hasattr(fe_det_resp, "Observaciones") and fe_det_resp.Observaciones:
            observaciones = [
                Observacion(code=obs.Code, msg=obs.Msg)
                for obs in self._normalizar_lista(fe_det_resp.Observaciones.Obs)
            ]

        # Crear respuesta
        cae_response = CAEResponse(
            cae=fe_det_resp.CAE if hasattr(fe_det_resp, "CAE") else None,
            cae_vencimiento=(
                fe_det_resp.CAEFchVto if hasattr(fe_det_resp, "CAEFchVto") else None
            ),
            numero_comprobante=comprobante.cbte_desde,
            tipo_cbte=comprobante.tipo_cbte,
            punto_venta=comprobante.punto_venta,
            resultado=fe_det_resp.Resultado,
            observaciones=observaciones,
            errores=errores,
        )

        return cae_response

    @staticmethod
    def _normalizar_lista(valor) -> list:
        """Normaliza respuestas SOAP que pueden venir como item o lista."""
        if valor is None:
            return []
        if isinstance(valor, list):
            return valor
        return [valor]

    def _parse_errors_response(self, response) -> list[ErrorArca]:
        """Extrae errores globales de una respuesta WSFE."""
        if not hasattr(response, "Errors") or not response.Errors:
            return []

        return [
            ErrorArca(code=err.Code, msg=err.Msg)
            for err in self._normalizar_lista(response.Errors.Err)
        ]

    async def fe_comp_consultar(
        self, punto_venta: int, tipo_cbte: int, numero: int
    ) -> ComprobanteResponse:
        """
        Consulta un comprobante emitido.

        Args:
            punto_venta: Punto de venta
            tipo_cbte: Tipo de comprobante
            numero: Número de comprobante

        Returns:
            ComprobanteResponse con los datos del comprobante

        Raises:
            ArcaServiceError: Si hay error del servicio o no se encuentra
        """
        try:
            auth = self._get_auth_dict()

            response = await self._call_soap(
                "FECompConsultar",
                Auth=auth,
                FeCompConsReq={
                    "CbteTipo": tipo_cbte,
                    "CbteNro": numero,
                    "PtoVta": punto_venta,
                },
            )

            # Verificar errores
            if hasattr(response, "Errors") and response.Errors:
                error = (
                    response.Errors.Err[0]
                    if isinstance(response.Errors.Err, list)
                    else response.Errors.Err
                )
                raise ArcaServiceError(
                    f"Error al consultar comprobante: {error.Msg}",
                    codigo=str(error.Code),
                )

            # Parsear resultado
            result = response.ResultGet

            return ComprobanteResponse(
                punto_venta=result.PtoVta,
                tipo_cbte=result.CbteTipo,
                numero=getattr(result, "CbteNro", result.CbteDesde),
                cuit_emisor=(
                    str(result.CuitEmisor)
                    if hasattr(result, "CuitEmisor")
                    else self.cuit
                ),
                cae=result.CodAutorizacion,
                cae_vencimiento=result.FchVto,
                fecha_cbte=result.CbteFch,
                fecha_proceso=result.FchProceso,
                imp_total=result.ImpTotal,
                imp_neto=result.ImpNeto,
                imp_iva=result.ImpIVA,
                imp_op_ex=result.ImpOpEx,
                imp_tot_conc=result.ImpTotConc,
                imp_trib=result.ImpTrib,
                moneda_id=result.MonId,
                moneda_cotiz=result.MonCotiz,
                tipo_doc=result.DocTipo,
                nro_doc=result.DocNro,
                resultado=result.Resultado,
            )

        except Fault as e:
            raise ArcaServiceError(f"Error SOAP: {e.message}")
        except ArcaServiceError:
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error inesperado: {str(e)}")

    # ==================== Métodos de Parámetros ====================

    async def fe_param_get_tipos_cbte(self) -> List[TipoComprobante]:
        """
        Obtiene los tipos de comprobante disponibles.

        Returns:
            Lista de tipos de comprobante
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap("FEParamGetTiposCbte", Auth=auth)

            tipos = response.ResultGet.CbteTipo
            if not isinstance(tipos, list):
                tipos = [tipos]

            return [
                TipoComprobante(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None,
                )
                for t in tipos
            ]

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener tipos de comprobante: {str(e)}")

    async def fe_param_get_tipos_doc(self) -> List[TipoDocumento]:
        """
        Obtiene los tipos de documento disponibles.

        Returns:
            Lista de tipos de documento
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap("FEParamGetTiposDoc", Auth=auth)

            tipos = response.ResultGet.DocTipo
            if not isinstance(tipos, list):
                tipos = [tipos]

            return [
                TipoDocumento(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None,
                )
                for t in tipos
            ]

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener tipos de documento: {str(e)}")

    async def fe_param_get_tipos_iva(self) -> List[TipoIva]:
        """
        Obtiene las alícuotas de IVA disponibles.

        Returns:
            Lista de tipos de IVA
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap("FEParamGetTiposIva", Auth=auth)

            tipos = response.ResultGet.IvaTipo
            if not isinstance(tipos, list):
                tipos = [tipos]

            return [
                TipoIva(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None,
                )
                for t in tipos
            ]

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener tipos de IVA: {str(e)}")

    async def fe_param_get_tipos_concepto(self) -> List[TipoConcepto]:
        """
        Obtiene los tipos de concepto disponibles.

        Returns:
            Lista de tipos de concepto
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap("FEParamGetTiposConcepto", Auth=auth)

            tipos = response.ResultGet.ConceptoTipo
            if not isinstance(tipos, list):
                tipos = [tipos]

            return [
                TipoConcepto(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None,
                )
                for t in tipos
            ]

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener tipos de concepto: {str(e)}")

    async def fe_param_get_tipos_monedas(self) -> List[TipoMoneda]:
        """
        Obtiene los tipos de moneda disponibles.

        Returns:
            Lista de tipos de moneda
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap("FEParamGetTiposMonedas", Auth=auth)

            tipos = response.ResultGet.Moneda
            if not isinstance(tipos, list):
                tipos = [tipos]

            return [
                TipoMoneda(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None,
                )
                for t in tipos
            ]

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener tipos de moneda: {str(e)}")

    async def fe_param_get_cotizacion(self, moneda_id: str) -> Cotizacion:
        """
        Obtiene la cotización de una moneda.

        Args:
            moneda_id: ID de la moneda (ej: "DOL")

        Returns:
            Cotización de la moneda
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap(
                "FEParamGetCotizacion",
                Auth=auth,
                MonId=moneda_id,
            )

            result = response.ResultGet

            return Cotizacion(
                moneda_id=result.MonId,
                cotizacion=result.MonCotiz,
                fecha=result.FchCotiz,
            )

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener cotización: {str(e)}")

    async def fe_param_get_ptos_venta(self) -> List[PuntoVenta]:
        """
        Obtiene los puntos de venta habilitados.

        Returns:
            Lista de puntos de venta
        """
        try:
            auth = self._get_auth_dict()
            response = await self._call_soap("FEParamGetPtosVenta", Auth=auth)

            if hasattr(response, "Errors") and response.Errors:
                err_list = response.Errors.Err
                if not isinstance(err_list, list):
                    err_list = [err_list]

                # En homologación ARCA puede responder "Sin Resultados" aunque
                # FECompUltimoAutorizado funcione correctamente para el punto.
                if all(getattr(err, "Code", None) == 602 for err in err_list):
                    return []

                error = err_list[0]
                raise ArcaServiceError(
                    f"Error al obtener puntos de venta: {error.Msg}",
                    codigo=str(error.Code),
                )

            if response.ResultGet is None:
                return []

            ptos = response.ResultGet.PtoVenta
            if not isinstance(ptos, list):
                ptos = [ptos]

            def normalizar_fecha_baja(valor) -> str | None:
                if valor is None:
                    return None
                texto = str(valor).strip()
                if not texto or texto.upper() == "NULL":
                    return None
                return texto

            return [
                PuntoVenta(
                    numero=p.Nro,
                    emision_tipo=p.EmisionTipo,
                    bloqueado=p.Bloqueado,
                    fecha_baja=normalizar_fecha_baja(
                        p.FchBaja if hasattr(p, "FchBaja") else None
                    ),
                )
                for p in ptos
            ]

        except Exception as e:
            raise ArcaServiceError(f"Error al obtener puntos de venta: {str(e)}")
