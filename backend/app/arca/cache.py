"""Cache para tickets de acceso de ARCA."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional

from app.arca.models import TicketAcceso


class TokenCache:
    """
    Cache en memoria para tickets de acceso de ARCA.

    Los tickets de WSAA tienen validez de hasta 12 horas. Este cache permite
    reutilizar tokens válidos y evitar autenticaciones innecesarias.
    """

    def __init__(self):
        """Inicializa el cache."""
        self._cache: Dict[str, TicketAcceso] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[TicketAcceso]:
        """
        Obtiene un ticket del cache.

        Args:
            key: Clave del cache (ej: "wsfe_20123456789_homologacion")

        Returns:
            TicketAcceso si existe y es válido, None en caso contrario
        """
        async with self._lock:
            ticket = self._cache.get(key)

            if ticket is None:
                return None

            # Verificar si está expirado (con margen de 5 minutos)
            if ticket.is_expired() or self._is_near_expiration(ticket):
                del self._cache[key]
                return None

            return ticket

    async def set(self, key: str, ticket: TicketAcceso) -> None:
        """
        Guarda un ticket en el cache.

        Args:
            key: Clave del cache
            ticket: Ticket a guardar
        """
        async with self._lock:
            self._cache[key] = ticket

    async def delete(self, key: str) -> None:
        """
        Elimina un ticket del cache.

        Args:
            key: Clave del cache
        """
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Limpia todo el cache."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """
        Elimina todos los tickets expirados del cache.

        Returns:
            Cantidad de tickets eliminados
        """
        async with self._lock:
            expired_keys = [
                key for key, ticket in self._cache.items() if ticket.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def _is_near_expiration(
        self, ticket: TicketAcceso, margin_minutes: int = 5
    ) -> bool:
        """
        Verifica si un ticket está cerca de expirar.

        Args:
            ticket: Ticket a verificar
            margin_minutes: Margen de tiempo en minutos

        Returns:
            True si está cerca de expirar
        """
        now = datetime.utcnow()
        expiration_threshold = ticket.expiracion - timedelta(minutes=margin_minutes)
        return now >= expiration_threshold

    def get_cache_key(self, servicio: str, cuit: str, ambiente: str) -> str:
        """
        Genera una clave de cache.

        Args:
            servicio: Servicio (ej: "wsfe")
            cuit: CUIT de la empresa
            ambiente: Ambiente (homologacion/produccion)

        Returns:
            Clave de cache
        """
        return f"{servicio}_{cuit}_{ambiente}"


# Instancia global del cache
_token_cache = TokenCache()


def get_token_cache() -> TokenCache:
    """
    Obtiene la instancia global del cache de tokens.

    Returns:
        Instancia de TokenCache
    """
    return _token_cache
