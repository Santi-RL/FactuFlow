# Integración ARCA

## Nomenclatura
- ARCA es el nombre actual y debe ser el preferido en documentación y UI.
- AFIP aparece en URLs y variables legacy por compatibilidad.

## Documentación oficial
- La documentación oficial de Web Services está en `https://www.arca.gob.ar/ws/`.
- Descargas e índice local: `docs/arca-ws/README.md`.

## Módulos relevantes
- `backend/app/arca/wsaa.py`: autenticación WSAA.
- `backend/app/arca/wsfev1.py`: factura electrónica WSFEv1.
- `backend/app/arca/crypto.py`: firmado y utilidades criptográficas.
- `backend/app/arca/config.py`: configuración ARCA.
- `backend/app/arca/cache.py`: cache de credenciales.
- `backend/app/arca/utils.py`: helpers.
- `backend/app/api/arca.py`: endpoints HTTP para ARCA.

## Endpoints oficiales (legacy AFIP)
- WSAA homologación: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSAA producción: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1 homologación: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- WSFEv1 producción: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

## Flujo WSAA básico
1. Generar TRA para el servicio (`wsfe`).
2. Firmar el TRA con la clave privada.
3. Enviar el CMS a `loginCms()`.
4. Usar Token y Sign en WSFEv1.

## Variables de entorno
- El entorno se define con `AFIP_ENV` y valores `homologacion` o `produccion`.
- El path de certificados se define con `CERTS_PATH`, con fallback a `AFIP_CERTS_PATH`.
- Si agregás nuevas variables públicas, preferí el prefijo `ARCA_` y mantené compatibilidad.
