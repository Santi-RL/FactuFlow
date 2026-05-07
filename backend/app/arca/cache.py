"""Cache para tickets de acceso de ARCA."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from app.arca.models import TicketAcceso
from app.core.config import settings


class TokenCache:
    """
    Cache en memoria para tickets de acceso de ARCA.

    Los tickets de WSAA tienen validez de hasta 12 horas. Este cache permite
    reutilizar tokens válidos y evitar autenticaciones innecesarias.
    """

    def __init__(self, storage_path: str | None = None):
        """Inicializa el cache."""
        self._cache: Dict[str, TicketAcceso] = {}
        self._lock = asyncio.Lock()
        self.storage_path = Path(storage_path or settings.arca_token_cache_path)
        self._load_from_disk()

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
                self._save_to_disk()
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
            self._save_to_disk()

    async def delete(self, key: str) -> None:
        """
        Elimina un ticket del cache.

        Args:
            key: Clave del cache
        """
        async with self._lock:
            self._cache.pop(key, None)
            self._save_to_disk()

    async def clear(self) -> None:
        """Limpia todo el cache."""
        async with self._lock:
            if self._cache:
                self._cache.clear()
                self._save_to_disk()

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

            if expired_keys:
                self._save_to_disk()

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
        now = datetime.now(timezone.utc)
        expiration = ticket.expiracion
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        expiration_threshold = expiration - timedelta(minutes=margin_minutes)
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

    def _load_from_disk(self) -> None:
        """Carga tickets persistidos desde disco si existen."""
        if not self.storage_path.exists():
            return

        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        for key, ticket_data in payload.items():
            if not isinstance(ticket_data, dict):
                continue
            try:
                ticket = TicketAcceso(**ticket_data)
            except Exception:
                continue

            if ticket.is_expired() or self._is_near_expiration(ticket):
                continue

            self._cache[key] = ticket

    def _save_to_disk(self) -> None:
        """Persist tickets vigentes para reutilizarlos entre reinicios."""
        valid_tickets = {
            key: ticket.model_dump(mode="json")
            for key, ticket in self._cache.items()
            if not ticket.is_expired() and not self._is_near_expiration(ticket)
        }

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if valid_tickets:
                self.storage_path.write_text(
                    json.dumps(valid_tickets, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
            elif self.storage_path.exists():
                self.storage_path.unlink()
        except OSError:
            # Si falla la persistencia, el cache en memoria sigue siendo usable.
            return


# Instancia global del cache
_token_cache = TokenCache()


def get_token_cache() -> TokenCache:
    """
    Obtiene la instancia global del cache de tokens.

    Returns:
        Instancia de TokenCache
    """
    return _token_cache
