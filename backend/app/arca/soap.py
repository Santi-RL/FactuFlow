"""Utilidades para clientes SOAP de ARCA."""

import ssl

import requests
from requests.adapters import HTTPAdapter
from zeep import Client
from zeep.transports import Transport


class ArcaTLSAdapter(HTTPAdapter):
    """Adaptador TLS compatible con endpoints legacy de ARCA."""

    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = context
        return super().proxy_manager_for(*args, **kwargs)


def create_soap_client(wsdl_url: str, timeout: int = 30) -> Client:
    """Crea un cliente SOAP con transporte TLS compatible con ARCA."""

    session = requests.Session()
    adapter = ArcaTLSAdapter()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    transport = Transport(session=session, timeout=timeout)
    return Client(wsdl_url, transport=transport)
