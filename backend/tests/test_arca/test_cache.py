"""Tests para el cache de tokens de ARCA."""

import os
import stat

import pytest
from datetime import datetime, timedelta, timezone

from app.arca.cache import TokenCache
from app.arca.models import TicketAcceso


@pytest.mark.asyncio
class TestTokenCache:
    """Tests para TokenCache."""

    def build_cache(self, tmp_path):
        """Crea una instancia aislada del cache para tests."""
        return TokenCache(storage_path=str(tmp_path / "arca-token-cache.json"))

    async def test_set_and_get_token(self, tmp_path):
        """Debe guardar y recuperar un token."""
        cache = self.build_cache(tmp_path)

        ticket = TicketAcceso(
            token="test_token",
            sign="test_sign",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfe",
        )

        await cache.set("test_key", ticket)
        retrieved = await cache.get("test_key")

        assert retrieved is not None
        assert retrieved.token == "test_token"
        assert retrieved.sign == "test_sign"

    async def test_get_nonexistent_key(self, tmp_path):
        """Debe devolver None para clave inexistente."""
        cache = self.build_cache(tmp_path)

        result = await cache.get("nonexistent_key")

        assert result is None

    async def test_get_expired_token(self, tmp_path):
        """Debe devolver None para token expirado."""
        cache = self.build_cache(tmp_path)

        # Token expirado hace 1 hora
        ticket = TicketAcceso(
            token="expired_token",
            sign="expired_sign",
            expiracion=datetime.now(timezone.utc) - timedelta(hours=1),
            servicio="wsfe",
        )

        await cache.set("expired_key", ticket)
        result = await cache.get("expired_key")

        assert result is None

    async def test_get_near_expiration_token(self, tmp_path):
        """Debe devolver None para token cerca de expirar."""
        cache = self.build_cache(tmp_path)

        # Token que expira en 3 minutos (menos del margen de 5 minutos)
        ticket = TicketAcceso(
            token="near_expiration_token",
            sign="near_expiration_sign",
            expiracion=datetime.now(timezone.utc) + timedelta(minutes=3),
            servicio="wsfe",
        )

        await cache.set("near_expiration_key", ticket)
        result = await cache.get("near_expiration_key")

        assert result is None

    async def test_delete_token(self, tmp_path):
        """Debe eliminar un token del cache."""
        cache = self.build_cache(tmp_path)

        ticket = TicketAcceso(
            token="test_token",
            sign="test_sign",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfe",
        )

        await cache.set("test_key", ticket)
        await cache.delete("test_key")
        result = await cache.get("test_key")

        assert result is None

    async def test_clear_cache(self, tmp_path):
        """Debe limpiar todo el cache."""
        cache = self.build_cache(tmp_path)

        ticket1 = TicketAcceso(
            token="token1",
            sign="sign1",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfe",
        )

        ticket2 = TicketAcceso(
            token="token2",
            sign="sign2",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfex",
        )

        await cache.set("key1", ticket1)
        await cache.set("key2", ticket2)
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    async def test_cleanup_expired(self, tmp_path):
        """Debe limpiar tokens expirados."""
        cache = self.build_cache(tmp_path)

        # Token válido
        valid_ticket = TicketAcceso(
            token="valid_token",
            sign="valid_sign",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfe",
        )

        # Token expirado
        expired_ticket = TicketAcceso(
            token="expired_token",
            sign="expired_sign",
            expiracion=datetime.now(timezone.utc) - timedelta(hours=1),
            servicio="wsfex",
        )

        await cache.set("valid_key", valid_ticket)
        await cache.set("expired_key", expired_ticket)

        # Limpiar expirados
        cleaned = await cache.cleanup_expired()

        assert cleaned == 1
        assert await cache.get("valid_key") is not None
        assert await cache.get("expired_key") is None

    async def test_persists_valid_tokens(self, tmp_path):
        """Debe persistir tickets vigentes y poder recargarlos."""
        cache = self.build_cache(tmp_path)
        ticket = TicketAcceso(
            token="persisted_token",
            sign="persisted_sign",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfe",
        )

        await cache.set("persisted_key", ticket)

        reloaded = self.build_cache(tmp_path)
        restored_ticket = await reloaded.get("persisted_key")

        assert restored_ticket is not None
        assert restored_ticket.token == "persisted_token"

    async def test_cache_file_uses_restrictive_permissions(self, tmp_path):
        """Debe persistir token/sign con permisos restrictivos cuando aplica."""
        cache = self.build_cache(tmp_path)
        ticket = TicketAcceso(
            token="persisted_token",
            sign="persisted_sign",
            expiracion=datetime.now(timezone.utc) + timedelta(hours=12),
            servicio="wsfe",
        )

        await cache.set("persisted_key", ticket)

        assert cache.storage_path.exists()
        if os.name == "posix":
            file_mode = stat.S_IMODE(cache.storage_path.stat().st_mode)
            assert file_mode == stat.S_IRUSR | stat.S_IWUSR

    def test_get_cache_key(self, tmp_path):
        """Debe generar clave de cache correcta."""
        cache = self.build_cache(tmp_path)

        key = cache.get_cache_key("wsfe", "20123456789", "homologacion")

        assert key == "wsfe_20123456789_homologacion"
