"""Cliente para el Web Service de Autenticación y Autorización (WSAA) de ARCA."""

import logging
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

from zeep import Client
from zeep.exceptions import Fault, TransportError

from app.arca.config import ArcaAmbiente, ArcaConfig
from app.arca.crypto import create_signed_tra
from app.arca.cache import get_token_cache
from app.arca.models import TicketAcceso
from app.arca.exceptions import ArcaAuthError, ArcaConnectionError
from app.arca.utils import clean_cuit


logger = logging.getLogger(__name__)


class WSAAClient:
    """
    Cliente para el Web Service de Autenticación y Autorización (WSAA).
    
    Este servicio permite autenticarse contra ARCA y obtener un ticket de acceso
    (token y sign) que luego se usa para otros webservices como WSFEv1.
    """
    
    def __init__(self, ambiente: ArcaAmbiente):
        """
        Inicializa el cliente WSAA.
        
        Args:
            ambiente: Ambiente de ARCA (homologacion o produccion)
        """
        self.config = ArcaConfig(ambiente=ambiente)
        self.cache = get_token_cache()
        
        # Cliente SOAP
        try:
            self.client = Client(self.config.wsaa_url)
        except Exception as e:
            raise ArcaConnectionError(f"Error al conectar con WSAA: {str(e)}")
    
    async def login(
        self,
        cert_path: str,
        key_path: str,
        cuit: str,
        servicio: str = "wsfe",
        key_password: Optional[bytes] = None,
        force_new: bool = False
    ) -> TicketAcceso:
        """
        Autentica contra WSAA y obtiene un ticket de acceso.
        
        Este método:
        1. Verifica si hay un ticket válido en cache
        2. Si no hay, genera un TRA (Ticket de Requerimiento de Acceso)
        3. Firma el TRA con el certificado X.509
        4. Llama al método loginCms del WSAA
        5. Parsea la respuesta y devuelve el ticket
        6. Cachea el ticket para reutilizarlo
        
        Args:
            cert_path: Ruta al archivo del certificado (.crt)
            key_path: Ruta al archivo de la clave privada (.key)
            cuit: CUIT de la empresa
            servicio: Servicio para el que se solicita el ticket (default: "wsfe")
            key_password: Contraseña de la clave privada (opcional)
            force_new: Forzar obtención de nuevo ticket ignorando cache
            
        Returns:
            TicketAcceso con token, sign y expiración
            
        Raises:
            ArcaAuthError: Si hay error en la autenticación
            ArcaConnectionError: Si hay error de conexión
        """
        cuit_clean = clean_cuit(cuit)
        
        # Verificar cache si no se fuerza nuevo ticket
        if not force_new:
            cache_key = self.cache.get_cache_key(servicio, cuit_clean, self.config.ambiente.value)
            cached_ticket = await self.cache.get(cache_key)
            
            if cached_ticket:
                logger.info(f"Usando ticket en cache para {servicio} - CUIT: {cuit_clean}")
                return cached_ticket
        
        logger.info(f"Solicitando nuevo ticket para {servicio} - CUIT: {cuit_clean}")
        
        try:
            # Crear TRA firmado
            cms = create_signed_tra(
                cert_path=cert_path,
                key_path=key_path,
                servicio=servicio,
                ttl_hours=12,
                key_password=key_password
            )
            
            # Llamar al webservice
            response = self.client.service.loginCms(cms)
            
            # Parsear respuesta
            ticket = self._parse_response(response, servicio)
            
            # Guardar en cache
            cache_key = self.cache.get_cache_key(servicio, cuit_clean, self.config.ambiente.value)
            await self.cache.set(cache_key, ticket)
            
            logger.info(f"Ticket obtenido exitosamente. Expira: {ticket.expiracion}")
            
            return ticket
            
        except Fault as e:
            error_msg = f"Error SOAP en WSAA: {e.message}"
            logger.error(error_msg)
            raise ArcaAuthError(error_msg)
            
        except TransportError as e:
            error_msg = f"Error de transporte en WSAA: {str(e)}"
            logger.error(error_msg)
            raise ArcaConnectionError(error_msg)
            
        except Exception as e:
            error_msg = f"Error inesperado en WSAA: {str(e)}"
            logger.error(error_msg)
            raise ArcaAuthError(error_msg)
    
    def _parse_response(self, response: str, servicio: str) -> TicketAcceso:
        """
        Parsea la respuesta XML del WSAA y extrae token, sign y expiración.
        
        Args:
            response: Respuesta XML del WSAA
            servicio: Servicio para el que se solicitó el ticket
            
        Returns:
            TicketAcceso con los datos extraídos
            
        Raises:
            ArcaAuthError: Si no se puede parsear la respuesta
        """
        try:
            # Parsear XML
            root = ET.fromstring(response)
            
            # Extraer token y sign
            credentials = root.find(".//credentials")
            if credentials is None:
                raise ArcaAuthError("No se encontró el elemento 'credentials' en la respuesta")
            
            token_elem = credentials.find("token")
            sign_elem = credentials.find("sign")
            
            if token_elem is None or sign_elem is None:
                raise ArcaAuthError("No se encontraron token o sign en la respuesta")
            
            token = token_elem.text
            sign = sign_elem.text
            
            # Extraer fecha de expiración
            header = root.find(".//header")
            if header is None:
                raise ArcaAuthError("No se encontró el elemento 'header' en la respuesta")
            
            expiration_elem = header.find("expirationTime")
            if expiration_elem is None:
                raise ArcaAuthError("No se encontró expirationTime en la respuesta")
            
            expiration_str = expiration_elem.text
            expiracion = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
            
            return TicketAcceso(
                token=token,
                sign=sign,
                expiracion=expiracion,
                servicio=servicio
            )
            
        except ET.ParseError as e:
            raise ArcaAuthError(f"Error al parsear respuesta XML: {str(e)}")
        except Exception as e:
            raise ArcaAuthError(f"Error al procesar respuesta del WSAA: {str(e)}")
    
    async def invalidate_cache(self, cuit: str, servicio: str = "wsfe") -> None:
        """
        Invalida el ticket en cache para un servicio y CUIT específico.
        
        Args:
            cuit: CUIT de la empresa
            servicio: Servicio (default: "wsfe")
        """
        cuit_clean = clean_cuit(cuit)
        cache_key = self.cache.get_cache_key(servicio, cuit_clean, self.config.ambiente.value)
        await self.cache.delete(cache_key)
        logger.info(f"Cache invalidado para {servicio} - CUIT: {cuit_clean}")
