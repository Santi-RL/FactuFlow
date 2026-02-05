# Documentación oficial ARCA WS (fuente de verdad)

Este directorio contiene descargas de la documentación pública de ARCA para Web Services. La fuente oficial y siempre actualizada es `https://www.arca.gob.ar/ws/`.

Fecha de descarga local: 2026-02-05.

## Capa consultable (recomendado)

- Notas rapidas: `docs/arca-ws/NOTAS.md`
- Generar una version buscable (texto extraido de PDFs y listados de ZIP/TGZ):

Requisito (instalar extractor PDF una sola vez):

```bash
python -m pip install --user --upgrade pdfminer.six
python -c "import pdfminer.high_level; print('pdfminer.six OK')"
```

```bash
python scripts/arca_ws_extract.py
rg -n "loginCms|TRA|FECAESolicitar" docs/arca-ws/_extracted
```

Nota: `docs/arca-ws/_extracted/` es output local y no se recomienda commitearlo.

## Índice de páginas oficiales (no descargadas)
- `https://www.arca.gob.ar/ws/`
- `https://www.arca.gob.ar/ws/programadores/`
- `https://www.arca.gob.ar/ws/programadores/entornos-disponibles.asp`
- `https://www.arca.gob.ar/ws/programadores/certificados-digitales.asp`
- `https://www.arca.gob.ar/ws/documentacion/`
- `https://www.arca.gob.ar/ws/documentacion/arquitectura.asp`
- `https://www.arca.gob.ar/ws/documentacion/autoridades-certificantes.asp`
- `https://www.arca.gob.ar/ws/documentacion/cronograma-tls.asp`
- `https://www.arca.gob.ar/ws/documentacion/servicios-migrados.asp`
- `https://www.arca.gob.ar/ws/documentacion/ws-ass-portal.asp`
- `https://www.arca.gob.ar/ws/documentacion/catalogo.asp`
- `https://www.arca.gob.ar/ws/documentacion/wsaa.asp`
- `https://www.arca.gob.ar/ws/documentacion/ws-factura-electronica.asp`
- `https://www.arca.gob.ar/ws/documentacion/certificados.asp`

## Descargas locales

**WSAA**
- `docs/arca-ws/wsaa/WSAA.ObtenerCertificado.pdf` — `https://www.arca.gob.ar/ws/WSAA/WSAA.ObtenerCertificado.pdf`
- `docs/arca-ws/wsaa/ADMINREL.DelegarWS.pdf` — `https://www.arca.gob.ar/ws/WSAA/ADMINREL.DelegarWS.pdf`
- `docs/arca-ws/wsaa/wsaa_obtener_certificado_produccion.pdf` — `https://www.arca.gob.ar/ws/WSAA/wsaa_obtener_certificado_produccion.pdf`
- `docs/arca-ws/wsaa/wsaa_asociar_certificado_a_wsn_produccion.pdf` — `https://www.arca.gob.ar/ws/WSAA/wsaa_asociar_certificado_a_wsn_produccion.pdf`
- `docs/arca-ws/wsaa/Especificacion_Tecnica_WSAA_1.2.2.pdf` — `https://www.arca.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.2.pdf`
- `docs/arca-ws/wsaa/WSAAmanualDev.pdf` — `https://www.arca.gob.ar/ws/WSAA/WSAAmanualDev.pdf`
- `docs/arca-ws/wsaa/wsaa_client_java.tgz` — `https://www.arca.gob.ar/ws/WSAA/ejemplos/wsaa_client_java.tgz`
- `docs/arca-ws/wsaa/wsaa-client-php.zip` — `https://www.arca.gob.ar/ws/WSAA/ejemplos/wsaa-client-php.zip`
- `docs/arca-ws/wsaa/dev-wsaa-cliente-dotnet-cs.zip` — `https://www.arca.gob.ar/ws/WSAA/ejemplos/dev-wsaa-cliente-dotnet-cs.zip`
- `docs/arca-ws/wsaa/dev-wsaa-cliente-dotnet-vb.zip` — `https://www.arca.gob.ar/ws/WSAA/ejemplos/dev-wsaa-cliente-dotnet-vb.zip`
- `docs/arca-ws/wsaa/dev-wsaa-cliente-powershell.zip` — `https://www.arca.gob.ar/ws/WSAA/ejemplos/dev-wsaa-cliente-powershell.zip`

**WSASS y certificados**
- `docs/arca-ws/wsass/WSASS_como_adherirse.pdf` — `https://www.arca.gob.ar/ws/WSASS/WSASS_como_adherirse.pdf`
- `docs/arca-ws/wsass/WSASS_manual.pdf` — `https://www.arca.gob.ar/ws/WSASS/WSASS_manual.pdf`
- `docs/arca-ws/wsass/WSASS_html_index.html` — `https://www.arca.gob.ar/ws/WSASS/html/index.html`
- `docs/arca-ws/certificados/Cadena_de_certificacion_homo_2014_2024.zip` — `https://www.arca.gob.ar/ws/WSASS/Cadena_de_certificacion_homo_2014_2024.zip`
- `docs/arca-ws/certificados/Cadena_de_certificacion_homo_2022_2034.zip` — `https://www.arca.gob.ar/ws/WSASS/Cadena_de_certificacion_homo_2022_2034.zip`
- `docs/arca-ws/certificados/Cadena_de_certificacion_prod_2016_2024.zip` — `https://www.arca.gob.ar/ws/documentacion/certificados/Cadena_de_certificacion_prod_2016_2024.zip`
- `docs/arca-ws/certificados/Cadena_de_certificacion_prod_2024_2035.zip` — `https://www.arca.gob.ar/ws/documentacion/certificados/Cadena_de_certificacion_prod_2024_2035.zip`

**Manualística WS (facturación y servicios relacionados)**
- `docs/arca-ws/wsfe/WSSEG-ManualParaElDesarrollador_ARCA.pdf` — `https://www.arca.gob.ar/ws/documentacion/manuales/WSSEG-ManualParaElDesarrollador_ARCA.pdf`
- `docs/arca-ws/wsfe/WSFEX-Manualparaeldesarrollador_V3.1.1_ARCA.pdf` — `https://www.arca.gob.ar/ws/documentacion/manuales/WSFEX-Manualparaeldesarrollador_V3.1.1_ARCA.pdf`
- `docs/arca-ws/wsfe/Manual_Desarrollador_WSCT_v1.6.4.pdf` — `https://www.arca.gob.ar/ws/documentacion/manuales/Manual_Desarrollador_WSCT_v1.6.4.pdf`
- `docs/arca-ws/wsfe/manual-desarrollador-ARCA-COMPG-v4-1.pdf` — `https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG-v4-1.pdf`
- `docs/arca-ws/wsfe/Web-Service-MTXCA-v25.pdf` — `https://www.arca.gob.ar/ws/documentacion/manuales/Web-Service-MTXCA-v25.pdf`

## Nota
Si ARCA actualiza manuales o URLs, actualizar esta carpeta y este índice. La URL base `https://www.arca.gob.ar/ws/` es la referencia oficial para el funcionamiento de los web services.
