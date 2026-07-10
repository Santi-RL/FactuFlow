"""Tests para las utilidades SOAP de ARCA."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
import time

import pytest

from app.arca import soap as soap_module
from app.arca.soap import create_soap_client, run_soap_call


def test_create_soap_client_configura_timeout_de_operacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El timeout debe cubrir WSDL y cada llamada SOAP."""

    captured: dict[str, object] = {}
    expected_client = object()

    class FakeTransport:
        """Captura la configuración sin abrir conexiones."""

        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    def fake_client(wsdl_url: str, *, transport: object) -> object:
        captured["wsdl_url"] = wsdl_url
        captured["transport"] = transport
        return expected_client

    monkeypatch.setattr(soap_module, "Transport", FakeTransport)
    monkeypatch.setattr(soap_module, "Client", fake_client)

    client = create_soap_client("https://arca.example.test/wsdl", timeout=17)

    assert client is expected_client
    assert captured["timeout"] == 17
    assert captured["operation_timeout"] == 17
    assert captured["wsdl_url"] == "https://arca.example.test/wsdl"


@pytest.mark.asyncio
async def test_run_soap_call_ejecuta_fuera_del_event_loop() -> None:
    """Una operación Zeep síncrona debe ejecutarse en un thread de trabajo."""

    event_loop_thread = threading.get_ident()

    def fake_soap_call(value: str, *, suffix: str) -> tuple[int, str]:
        return threading.get_ident(), f"{value}{suffix}"

    worker_thread, result = await run_soap_call(
        fake_soap_call,
        "ARCA",
        suffix="-OK",
    )

    assert worker_thread != event_loop_thread
    assert result == "ARCA-OK"


@pytest.mark.asyncio
async def test_run_soap_call_no_depende_de_keywords_nuevos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La llamada debe funcionar con la firma mínima disponible en AnyIO 3."""

    async def fake_run_sync(func: Callable[[], str]) -> str:
        return func()

    monkeypatch.setattr(soap_module.to_thread, "run_sync", fake_run_sync)

    assert await run_soap_call(lambda: "OK") == "OK"


@pytest.mark.asyncio
async def test_run_soap_call_no_bloquea_otras_coroutines() -> None:
    """Una operación SOAP lenta no debe detener el event loop."""

    def slow_soap_call() -> str:
        time.sleep(0.2)
        return "OK"

    started_at = time.perf_counter()
    soap_task = asyncio.create_task(run_soap_call(slow_soap_call))
    await asyncio.sleep(0.02)
    heartbeat_elapsed = time.perf_counter() - started_at

    assert heartbeat_elapsed < 0.1
    assert await soap_task == "OK"
