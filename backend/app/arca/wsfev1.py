"""Cliente para el Web Service de Factura Electrónica v1 (WSFEv1) de ARCA."""

import logging
from typing import List, Optional

from zeep import Client
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
    ErrorArca
)
from app.arca.exceptions import (
    ArcaServiceError,
    ArcaValidationError,
    ArcaConnectionError
)
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
            self.client = Client(self.config.wsfe_url)
        except Exception as e:
            raise ArcaConnectionError(f"Error al conectar con WSFEv1: {str(e)}")
    
    def _get_auth_dict(self) -> dict:
        """
        Obtiene el diccionario de autenticación para las llamadas SOAP.
        
        Returns:
            Dict con Token, Sign y Cuit
        """
        return {
            "Token": self.ticket.token,
            "Sign": self.ticket.sign,
            "Cuit": self.cuit
        }
    
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
            response = self.client.service.FEDummy()
            
            return {
                "app_server": response.AppServer,
                "db_server": response.DbServer,
                "auth_server": response.AuthServer
            }
            
        except TransportError as e:
            raise ArcaConnectionError(f"Error de conexión con WSFEv1: {str(e)}")
        except Exception as e:
            raise ArcaServiceError(f"Error en FEDummy: {str(e)}")
    
    async def fe_comp_ultimo_autorizado(
        self,
        punto_venta: int,
        tipo_cbte: int
    ) -> int:
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
            
            response = self.client.service.FECompUltimoAutorizado(
                Auth=auth,
                PtoVta=punto_venta,
                CbteTipo=tipo_cbte
            )
            
            # Verificar errores
            if hasattr(response, "Errors") and response.Errors:
                error = response.Errors.Err[0] if isinstance(response.Errors.Err, list) else response.Errors.Err
                raise ArcaServiceError(
                    f"Error al obtener último comprobante: {error.Msg}",
                    codigo=str(error.Code)
                )
            
            return response.CbteNro
            
        except Fault as e:
            raise ArcaServiceError(f"Error SOAP: {e.message}")
        except ArcaServiceError:
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error inesperado: {str(e)}")
    
    async def fe_cae_solicitar(
        self,
        comprobante: ComprobanteRequest
    ) -> CAEResponse:
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
            auth = self._get_auth_dict()
            
            # Construir request
            fe_cab_req = {
                "CantReg": 1,
                "PtoVta": comprobante.punto_venta,
                "CbteTipo": comprobante.tipo_cbte
            }
            
            # Construir detalle del comprobante
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
                "MonCotiz": comprobante.moneda_cotiz
            }
            
            # Agregar fechas de servicio si aplica
            if comprobante.fecha_serv_desde:
                fe_det["FchServDesde"] = comprobante.fecha_serv_desde
            if comprobante.fecha_serv_hasta:
                fe_det["FchServHasta"] = comprobante.fecha_serv_hasta
            if comprobante.fecha_vto_pago:
                fe_det["FchVtoPago"] = comprobante.fecha_vto_pago
            
            # Agregar IVA si hay
            if comprobante.iva:
                fe_det["Iva"] = [
                    {
                        "Id": iva.id,
                        "BaseImp": format_importe(iva.base_imp),
                        "Importe": format_importe(iva.importe)
                    }
                    for iva in comprobante.iva
                ]
            
            # Agregar tributos si hay
            if comprobante.tributos:
                fe_det["Tributos"] = [
                    {
                        "Id": trib.id,
                        "Desc": trib.descripcion,
                        "BaseImp": format_importe(trib.base_imp),
                        "Alic": trib.alic,
                        "Importe": format_importe(trib.importe)
                    }
                    for trib in comprobante.tributos
                ]
            
            # Llamar al servicio
            response = self.client.service.FECAESolicitar(
                Auth=auth,
                FeCAEReq={
                    "FeCabReq": fe_cab_req,
                    "FeDetReq": [fe_det]
                }
            )
            
            # Parsear respuesta
            return self._parse_cae_response(response, comprobante)
            
        except Fault as e:
            raise ArcaServiceError(f"Error SOAP: {e.message}")
        except (ArcaValidationError, ArcaServiceError):
            raise
        except Exception as e:
            raise ArcaServiceError(f"Error inesperado: {str(e)}")
    
    def _parse_cae_response(
        self,
        response,
        comprobante: ComprobanteRequest
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
        # Extraer resultado
        fe_det_resp = response.FeDetResp.FECAEDetResponse[0] if isinstance(
            response.FeDetResp.FECAEDetResponse, list
        ) else response.FeDetResp.FECAEDetResponse
        
        # Extraer observaciones
        observaciones = []
        if hasattr(fe_det_resp, "Observaciones") and fe_det_resp.Observaciones:
            obs_list = fe_det_resp.Observaciones.Obs
            if not isinstance(obs_list, list):
                obs_list = [obs_list]
            
            observaciones = [
                Observacion(code=obs.Code, msg=obs.Msg)
                for obs in obs_list
            ]
        
        # Extraer errores
        errores = []
        if hasattr(response, "Errors") and response.Errors:
            err_list = response.Errors.Err
            if not isinstance(err_list, list):
                err_list = [err_list]
            
            errores = [
                ErrorArca(code=err.Code, msg=err.Msg)
                for err in err_list
            ]
        
        # Crear respuesta
        cae_response = CAEResponse(
            cae=fe_det_resp.CAE if hasattr(fe_det_resp, "CAE") else None,
            cae_vencimiento=fe_det_resp.CAEFchVto if hasattr(fe_det_resp, "CAEFchVto") else None,
            numero_comprobante=comprobante.cbte_desde,
            tipo_cbte=comprobante.tipo_cbte,
            punto_venta=comprobante.punto_venta,
            resultado=fe_det_resp.Resultado,
            observaciones=observaciones,
            errores=errores
        )
        
        # Si fue rechazado, lanzar excepción
        if cae_response.is_rechazado:
            error_msgs = [f"[{e.code}] {e.msg}" for e in errores]
            obs_msgs = [f"[{o.code}] {o.msg}" for o in observaciones]
            
            all_msgs = error_msgs + obs_msgs
            raise ArcaValidationError(
                f"Comprobante rechazado: {'; '.join(all_msgs)}"
            )
        
        return cae_response
    
    async def fe_comp_consultar(
        self,
        punto_venta: int,
        tipo_cbte: int,
        numero: int
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
            
            response = self.client.service.FECompConsultar(
                Auth=auth,
                FeCompConsReq={
                    "CbteTipo": tipo_cbte,
                    "CbteNro": numero,
                    "PtoVta": punto_venta
                }
            )
            
            # Verificar errores
            if hasattr(response, "Errors") and response.Errors:
                error = response.Errors.Err[0] if isinstance(response.Errors.Err, list) else response.Errors.Err
                raise ArcaServiceError(
                    f"Error al consultar comprobante: {error.Msg}",
                    codigo=str(error.Code)
                )
            
            # Parsear resultado
            result = response.ResultGet
            
            return ComprobanteResponse(
                punto_venta=result.PtoVta,
                tipo_cbte=result.CbteTipo,
                numero=result.CbteNro,
                cuit_emisor=str(result.CuitEmisor) if hasattr(result, "CuitEmisor") else self.cuit,
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
                resultado=result.Resultado
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
            response = self.client.service.FEParamGetTiposCbte(Auth=auth)
            
            tipos = response.ResultGet.CbteTipo
            if not isinstance(tipos, list):
                tipos = [tipos]
            
            return [
                TipoComprobante(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None
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
            response = self.client.service.FEParamGetTiposDoc(Auth=auth)
            
            tipos = response.ResultGet.DocTipo
            if not isinstance(tipos, list):
                tipos = [tipos]
            
            return [
                TipoDocumento(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None
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
            response = self.client.service.FEParamGetTiposIva(Auth=auth)
            
            tipos = response.ResultGet.IvaTipo
            if not isinstance(tipos, list):
                tipos = [tipos]
            
            return [
                TipoIva(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None
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
            response = self.client.service.FEParamGetTiposConcepto(Auth=auth)
            
            tipos = response.ResultGet.ConceptoTipo
            if not isinstance(tipos, list):
                tipos = [tipos]
            
            return [
                TipoConcepto(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None
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
            response = self.client.service.FEParamGetTiposMonedas(Auth=auth)
            
            tipos = response.ResultGet.Moneda
            if not isinstance(tipos, list):
                tipos = [tipos]
            
            return [
                TipoMoneda(
                    id=t.Id,
                    descripcion=t.Desc,
                    fecha_desde=t.FchDesde,
                    fecha_hasta=t.FchHasta if hasattr(t, "FchHasta") else None
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
            response = self.client.service.FEParamGetCotizacion(
                Auth=auth,
                MonId=moneda_id
            )
            
            result = response.ResultGet
            
            return Cotizacion(
                moneda_id=result.MonId,
                cotizacion=result.MonCotiz,
                fecha=result.FchCotiz
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
            response = self.client.service.FEParamGetPtosVenta(Auth=auth)
            
            ptos = response.ResultGet.PtoVenta
            if not isinstance(ptos, list):
                ptos = [ptos]
            
            return [
                PuntoVenta(
                    numero=p.Nro,
                    emision_tipo=p.EmisionTipo,
                    bloqueado=p.Bloqueado,
                    fecha_baja=p.FchBaja if hasattr(p, "FchBaja") else None
                )
                for p in ptos
            ]
            
        except Exception as e:
            raise ArcaServiceError(f"Error al obtener puntos de venta: {str(e)}")
