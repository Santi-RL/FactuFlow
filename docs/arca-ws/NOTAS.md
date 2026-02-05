# ARCA WS - Notas Rapidas (Consultable)

Este archivo es una capa "consultable" encima de la documentacion oficial descargada (PDF/ZIP/TGZ) en `docs/arca-ws/`.

Objetivo: poder ubicar rapido donde esta cada cosa y tener un resumen corto de lo que solemos consultar durante el desarrollo.

## Como buscar en la documentacion (recomendado)

La mayoria de los manuales oficiales estan en PDF, por lo que no se pueden buscar comodamente con `rg` sin una extraccion previa.

### Requisitos (una sola vez por maquina)

Instalar un extractor de PDF para que `scripts/arca_ws_extract.py` pueda convertir PDFs a texto.

Opcion recomendada (Windows/macOS/Linux):

```bash
python -m pip install --user --upgrade pdfminer.six
```

Verificacion:

```bash
python -c "import pdfminer.high_level; print('pdfminer.six OK')"
```

1. Generar textos extraidos (local, no se commitea):

```bash
python scripts/arca_ws_extract.py
```

2. Buscar con ripgrep:

```bash
rg -n "loginCms|TRA|Token|Sign|FECAESolicitar|FEDummy" docs/arca-ws/_extracted
```

Nota: si no se puede extraer texto (faltan dependencias), el script igual genera indices y listados de archivos dentro de ZIP/TGZ.

## WSAA (autenticacion)

Uso tipico:

1. Generar un TRA (Ticket de Requerimiento de Acceso) para el servicio (por ejemplo `wsfe`).
2. Firmar el TRA (CMS/PKCS#7) con el certificado X.509 y la clave privada.
3. Enviar el CMS a `loginCms()` del WSAA.
4. Usar `Token` y `Sign` para invocar el WS destino (por ejemplo WSFEv1).

Documentos locales:

- Especificacion tecnica: `docs/arca-ws/wsaa/Especificacion_Tecnica_WSAA_1.2.2.pdf`
- Manual dev: `docs/arca-ws/wsaa/WSAAmanualDev.pdf`
- Guia certificados/relaciones: `docs/arca-ws/wsaa/WSAA.ObtenerCertificado.pdf`
- Admin de relaciones: `docs/arca-ws/wsaa/ADMINREL.DelegarWS.pdf`

Ejemplos oficiales (archivos):

- Java: `docs/arca-ws/wsaa/wsaa_client_java.tgz`
- PHP: `docs/arca-ws/wsaa/wsaa-client-php.zip`
- .NET: `docs/arca-ws/wsaa/dev-wsaa-cliente-dotnet-cs.zip`, `docs/arca-ws/wsaa/dev-wsaa-cliente-dotnet-vb.zip`
- PowerShell: `docs/arca-ws/wsaa/dev-wsaa-cliente-powershell.zip`

## WSFE y servicios relacionados (manualistica)

En este repo la integracion implementada es WSFEv1 (factura electronica) en `backend/app/arca/wsfev1.py`.

Manuales locales relevantes:

- WSFE (varios): `docs/arca-ws/wsfe/`
  - `docs/arca-ws/wsfe/Web-Service-MTXCA-v25.pdf`
  - `docs/arca-ws/wsfe/manual-desarrollador-ARCA-COMPG-v4-1.pdf`
  - `docs/arca-ws/wsfe/Manual_Desarrollador_WSCT_v1.6.4.pdf`
- Otros WS (si se agregan mas adelante):
  - `docs/arca-ws/wsfe/WSFEX-Manualparaeldesarrollador_V3.1.1_ARCA.pdf` (exportacion)
  - `docs/arca-ws/wsfe/WSSEG-ManualParaElDesarrollador_ARCA.pdf`

## WSASS / Portal / Certificados (cadena y guias)

- Introduccion (ya esta en Markdown): `docs/arca-ws/wsass/introduccion-servicios.md`
- Guia: `docs/arca-ws/wsass/WSASS_como_adherirse.pdf`
- Manual: `docs/arca-ws/wsass/WSASS_manual.pdf`
- HTML de referencia: `docs/arca-ws/wsass/WSASS_html_index.html`

Cadena de certificacion (descargas ZIP):

- Homologacion: `docs/arca-ws/certificados/`
- Produccion: `docs/arca-ws/certificados/`

## URLs y nomenclatura

- El organismo es ARCA, pero muchas URLs siguen usando `afip.gov.ar` por compatibilidad tecnica.
- Para endpoints y variables legacy ver `docs/agents/arca.md` y el modulo `backend/app/arca/config.py`.
