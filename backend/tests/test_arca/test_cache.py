"""Tests para el cache de tokens de ARCA."""

import pytest
from datetime import datetime, timedelta

from app.arca.cache import TokenCache
from app.arca.models import TicketAcceso


@pytest.mark.asyncio
class TestTokenCache:
    """Tests para TokenCache."""

    async def test_set_and_get_token(self):
        """Debe guardar y recuperar un token."""
        cache = TokenCache()

        ticket = TicketAcceso(
            token="test_token",
            sign="test_sign",
            expiracion=datetime.utcnow() + timedelta(hours=12),
            servicio="wsfe",
        )

        await cache.set("test_key", ticket)
        retrieved = await cache.get("test_key")

        assert retrieved is not None
        assert retrieved.token == "test_token"
        assert retrieved.sign == "test_sign"

    async def test_get_nonexistent_key(self):
        """Debe devolver None para clave inexistente."""
        cache = TokenCache()

        result = await cache.get("nonexistent_key")

        assert result is None

    async def test_get_expired_token(self):
        """Debe devolver None para token expirado."""
        cache = TokenCache()

        # Token expirado hace 1 hora
        ticket = TicketAcceso(
            token="expired_token",
            sign="expired_sign",
            expiracion=datetime.utcnow() - timedelta(hours=1),
            servicio="wsfe",
        )

        await cache.set("expired_key", ticket)
        result = await cache.get("expired_key")

        assert result is None

    async def test_get_near_expiration_token(self):
        """Debe devolver None para token cerca de expirar."""
        cache = TokenCache()

        # Token que expira en 3 minutos (menos del margen de 5 minutos)
        ticket = TicketAcceso(
            token="near_expiration_token",
            sign="near_expiration_sign",
            expiracion=datetime.utcnow() + timedelta(minutes=3),
            servicio="wsfe",
        )

        await cache.set("near_expiration_key", ticket)
        result = await cache.get("near_expiration_key")

        assert result is None

    async def test_delete_token(self):
        """Debe eliminar un token del cache."""
        cache = TokenCache()

        ticket = TicketAcceso(
            token="test_token",
            sign="test_sign",
            expiracion=datetime.utcnow() + timedelta(hours=12),
            servicio="wsfe",
        )

        await cache.set("test_key", ticket)
        await cache.delete("test_key")
        result = await cache.get("test_key")

        assert result is None

    async def test_clear_cache(self):
        """Debe limpiar todo el cache."""
        cache = TokenCache()

        ticket1 = TicketAcceso(
            token="token1",
            sign="sign1",
            expiracion=datetime.utcnow() + timedelta(hours=12),
            servicio="wsfe",
        )

        ticket2 = TicketAcceso(
            token="token2",
            sign="sign2",
            expiracion=datetime.utcnow() + timedelta(hours=12),
            servicio="wsfex",
        )

        await cache.set("key1", ticket1)
        await cache.set("key2", ticket2)
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    async def test_cleanup_expired(self):
        """Debe limpiar tokens expirados."""
        cache = TokenCache()

        # Token válido
        valid_ticket = TicketAcceso(
            token="valid_token",
            sign="valid_sign",
            expiracion=datetime.utcnow() + timedelta(hours=12),
            servicio="wsfe",
        )

        # Token expirado
        expired_ticket = TicketAcceso(
            token="expired_token",
            sign="expired_sign",
            expiracion=datetime.utcnow() - timedelta(hours=1),
            servicio="wsfex",
        )

        await cache.set("valid_key", valid_ticket)
        await cache.set("expired_key", expired_ticket)

        # Limpiar expirados
        cleaned = await cache.cleanup_expired()

        assert cleaned == 1
        assert await cache.get("valid_key") is not None
        assert await cache.get("expired_key") is None

    def test_get_cache_key(self):
        """Debe generar clave de cache correcta."""
        cache = TokenCache()

        key = cache.get_cache_key("wsfe", "20123456789", "homologacion")

        assert key == "wsfe_20123456789_homologacion"
