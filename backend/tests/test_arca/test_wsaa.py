"""Tests para el cliente WSAA de ARCA."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.arca import wsaa as wsaa_module
from app.arca.cache import TokenCache
from app.arca.config import ArcaAmbiente
from app.arca.wsaa import WSAAClient


def _wsaa_response(token: str) -> str:
    """Construye una respuesta WSAA mínima para tests."""
    expiration = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return f"""
    <loginTicketResponse>
        <header>
            <expirationTime>{expiration}</expirationTime>
        </header>
        <credentials>
            <token>{token}</token>
            <sign>sign-{token}</sign>
        </credentials>
    </loginTicketResponse>
    """


@pytest.mark.asyncio
async def test_login_no_reutiliza_cache_entre_certificados_del_mismo_cuit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Un ticket WSAA queda scopiado al certificado que lo generó."""
    cert_activo = tmp_path / "cert-activo.crt"
    key_activo = tmp_path / "cert-activo.key"
    cert_verificado = tmp_path / "cert-verificado.crt"
    key_verificado = tmp_path / "cert-verificado.key"
    cert_activo.write_bytes(b"certificado activo")
    key_activo.write_bytes(b"key activo")
    cert_verificado.write_bytes(b"certificado verificado")
    key_verificado.write_bytes(b"key verificado")

    signed_cert_paths: list[str] = []

    def fake_create_signed_tra(**kwargs):
        signed_cert_paths.append(kwargs["cert_path"])
        return f"cms:{Path(kwargs['cert_path']).name}"

    soap_responses = iter(
        [_wsaa_response("token-verificado"), _wsaa_response("token-activo")]
    )
    soap_calls: list[str] = []

    def fake_login_cms(cms: str) -> str:
        soap_calls.append(cms)
        return next(soap_responses)

    monkeypatch.setattr(wsaa_module, "create_signed_tra", fake_create_signed_tra)

    client = WSAAClient.__new__(WSAAClient)
    client.config = SimpleNamespace(ambiente=ArcaAmbiente.HOMOLOGACION)
    client.cache = TokenCache(storage_path=str(tmp_path / "arca-token-cache.json"))
    client.client = SimpleNamespace(service=SimpleNamespace(loginCms=fake_login_cms))

    ticket_verificado = await client.login(
        cert_path=str(cert_verificado),
        key_path=str(key_verificado),
        cuit="20-12345678-9",
        servicio="wsfe",
        force_new=True,
    )
    ticket_activo = await client.login(
        cert_path=str(cert_activo),
        key_path=str(key_activo),
        cuit="20123456789",
        servicio="wsfe",
    )
    ticket_activo_replay = await client.login(
        cert_path=str(cert_activo),
        key_path=str(key_activo),
        cuit="20123456789",
        servicio="wsfe",
    )

    assert ticket_verificado.token == "token-verificado"
    assert ticket_activo.token == "token-activo"
    assert ticket_activo_replay.token == "token-activo"
    assert [Path(path).name for path in signed_cert_paths] == [
        cert_verificado.name,
        cert_activo.name,
    ]
    assert soap_calls == [f"cms:{cert_verificado.name}", f"cms:{cert_activo.name}"]
