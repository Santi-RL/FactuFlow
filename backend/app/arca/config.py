"""Configuración de URLs y ambientes para ARCA."""

from enum import Enum
from pydantic import BaseModel


class ArcaAmbiente(str, Enum):
    """Ambientes disponibles de ARCA."""
    
    HOMOLOGACION = "homologacion"
    PRODUCCION = "produccion"


class ArcaConfig(BaseModel):
    """Configuración de webservices de ARCA."""
    
    ambiente: ArcaAmbiente
    
    @property
    def wsaa_url(self) -> str:
        """
        URL del Web Service de Autenticación y Autorización (WSAA).
        
        Returns:
            URL del WSDL de WSAA según el ambiente
        """
        if self.ambiente == ArcaAmbiente.HOMOLOGACION:
            return "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
        return "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
    
    @property
    def wsfe_url(self) -> str:
        """
        URL del Web Service de Factura Electrónica v1 (WSFEv1).
        
        Returns:
            URL del WSDL de WSFEv1 según el ambiente
        """
        if self.ambiente == ArcaAmbiente.HOMOLOGACION:
            return "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
        return "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"
    
    @property
    def is_produccion(self) -> bool:
        """
        Verifica si está en ambiente de producción.
        
        Returns:
            True si es producción, False si es homologación
        """
        return self.ambiente == ArcaAmbiente.PRODUCCION
