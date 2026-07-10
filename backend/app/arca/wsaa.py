"""Cliente para el Web Service de Autenticación y Autorización (WSAA) de ARCA."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from zeep.exceptions import Fault, TransportError

from app.arca.config import ArcaAmbiente, ArcaConfig
from app.arca.crypto import create_signed_tra
from app.arca.cache import get_token_cache
from app.arca.models import TicketAcceso
from app.arca.exceptions import ArcaAuthError, ArcaConnectionError
from app.arca.soap import create_soap_client, run_soap_call
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
            self.client = create_soap_client(self.config.wsaa_url)
        except Exception as e:
            raise ArcaConnectionError(f"Error al conectar con WSAA: {str(e)}")

    async def login(
        self,
        cert_path: str,
        key_path: str,
        cuit: str,
        servicio: str = "wsfe",
        key_password: Optional[bytes] = None,
        force_new: bool = False,
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
        cert_fingerprint = self._certificate_fingerprint(cert_path)
        cache_key = self.cache.get_cache_key(
            servicio, cuit_clean, self.config.ambiente.value, cert_fingerprint
        )

        # Verificar cache si no se fuerza nuevo ticket
        if not force_new:
            cached_ticket = await self.cache.get(cache_key)

            if cached_ticket:
                logger.info(
                    f"Usando ticket en cache para {servicio} - CUIT: {cuit_clean}"
                )
                return cached_ticket

        logger.info(f"Solicitando nuevo ticket para {servicio} - CUIT: {cuit_clean}")

        try:
            # Crear TRA firmado
            cms = create_signed_tra(
                cert_path=cert_path,
                key_path=key_path,
                servicio=servicio,
                ttl_hours=12,
                key_password=key_password,
            )

            # Llamar al webservice sin bloquear el event loop.
            response = await run_soap_call(self.client.service.loginCms, cms)

            # Parsear respuesta
            ticket = self._parse_response(response, servicio)

            # Guardar en cache bajo la identidad del certificado usado.
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
                raise ArcaAuthError(
                    "No se encontró el elemento 'credentials' en la respuesta"
                )

            token_elem = credentials.find("token")
            sign_elem = credentials.find("sign")

            if token_elem is None or sign_elem is None:
                raise ArcaAuthError("No se encontraron token o sign en la respuesta")

            token = token_elem.text
            sign = sign_elem.text

            # Extraer fecha de expiración
            header = root.find(".//header")
            if header is None:
                raise ArcaAuthError(
                    "No se encontró el elemento 'header' en la respuesta"
                )

            expiration_elem = header.find("expirationTime")
            if expiration_elem is None:
                raise ArcaAuthError("No se encontró expirationTime en la respuesta")

            expiration_str = expiration_elem.text
            expiracion = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))

            return TicketAcceso(
                token=token, sign=sign, expiracion=expiracion, servicio=servicio
            )

        except ET.ParseError as e:
            raise ArcaAuthError(f"Error al parsear respuesta XML: {str(e)}")
        except Exception as e:
            raise ArcaAuthError(f"Error al procesar respuesta del WSAA: {str(e)}")

    def _certificate_fingerprint(self, cert_path: str) -> str:
        """Calcula la huella SHA-256 del certificado usado para WSAA."""
        try:
            return hashlib.sha256(Path(cert_path).read_bytes()).hexdigest()
        except OSError as exc:
            raise ArcaAuthError(
                "No se pudo leer el certificado para autenticar con ARCA"
            ) from exc

    async def invalidate_cache(
        self, cuit: str, servicio: str = "wsfe", cert_path: str | None = None
    ) -> None:
        """
        Invalida tickets en cache para un servicio, CUIT y certificado.

        Args:
            cuit: CUIT de la empresa
            servicio: Servicio (default: "wsfe")
            cert_path: Certificado concreto a invalidar. Si se omite, elimina
                todos los tickets versionados para el CUIT, ambiente y servicio.
        """
        cuit_clean = clean_cuit(cuit)
        ambiente = self.config.ambiente.value
        if cert_path:
            cache_key = self.cache.get_cache_key(
                servicio,
                cuit_clean,
                ambiente,
                self._certificate_fingerprint(cert_path),
            )
            await self.cache.delete(cache_key)
        else:
            await self.cache.delete_prefix(
                self.cache.get_cache_prefix(servicio, cuit_clean, ambiente)
            )
            await self.cache.delete(f"{servicio}_{cuit_clean}_{ambiente}")
        logger.info(f"Cache invalidado para {servicio} - CUIT: {cuit_clean}")
