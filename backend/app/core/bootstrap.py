"""Sincronización del bootstrap inicial de FactuFlow."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BOOTSTRAP_LOCK = asyncio.Lock()


async def tomar_lock_bootstrap(db: AsyncSession) -> None:
    """Toma un lock transaccional de bootstrap cuando la base lo soporta."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": "factuflow:bootstrap"},
    )
