"""Ciclo de vida del worker y del pool sin hooks obsoletos."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

import app.main as main


@pytest.mark.parametrize("fallo", [False, True])
async def test_lifespan_detiene_worker_y_libera_pool_ante_salida(monkeypatch, fallo):
    """El worker inicia una vez y los recursos se cierran aun si falla la app."""
    iniciar = Mock()
    detener = AsyncMock()
    disponer = AsyncMock()
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "ensure_lote_worker_running", iniciar)
    monkeypatch.setattr(main, "stop_lote_worker", detener)
    monkeypatch.setattr(main, "dispose_database_engines", disponer)
    application = FastAPI()
    try:
        async with main.lifespan(application):
            iniciar.assert_called_once_with(application)
            assert application.state.lotes_background_tasks == set()
            detener.assert_not_awaited()
            if fallo:
                raise RuntimeError("fallo sintético")
    except RuntimeError:
        assert fallo
    detener.assert_awaited_once_with(application)
    disponer.assert_awaited_once()


async def test_lifespan_libera_pool_si_falla_cierre_del_worker(monkeypatch):
    """Una excepción al detener el worker no deja el pool sin cerrar."""
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main, "ensure_lote_worker_running", Mock())
    monkeypatch.setattr(main, "stop_lote_worker", AsyncMock(side_effect=RuntimeError))
    disponer = AsyncMock()
    monkeypatch.setattr(main, "dispose_database_engines", disponer)
    with pytest.raises(RuntimeError):
        async with main.lifespan(FastAPI()):
            pass
    disponer.assert_awaited_once()
