# AFIP - Integración con Webservices

Esta carpeta contiene toda la integración con los webservices de AFIP.

## Componentes

### wsaa.py - Web Service de Autenticación y Autorización
Cliente para WSAA que gestiona la autenticación con AFIP:
- Generación de TRA (Ticket de Requerimiento de Acceso)
- Firma del TRA con certificado X.509
- Obtención de Token y Sign
- Cache de credenciales válidas

### wsfe.py - Web Service de Factura Electrónica v1
Cliente para WSFEv1 que permite:
- Emitir comprobantes (FECAESolicitar)
- Consultar último comprobante autorizado (FECompUltimoAutorizado)
- Consultar comprobantes (FECompConsultar)
- Obtener parámetros (tipos de comprobante, IVA, monedas, etc.)

### soap_client.py - Cliente SOAP Genérico
Cliente SOAP base que encapsula:
- Configuración de zeep/suds
- Manejo de timeouts y reintentos
- Logging de requests/responses
- Cache de WSDL

### exceptions.py - Excepciones AFIP
Excepciones personalizadas para errores de AFIP:
- `AFIPAuthError` - Error de autenticación
- `AFIPValidationError` - Error de validación de datos
- `AFIPConnectionError` - Error de conexión
- `AFIPServiceError` - Error del servicio

## Configuración

Los webservices de AFIP tienen URLs diferentes según el ambiente:

**Homologación (testing):**
- WSAA: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`

**Producción:**
- WSAA: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

Controlado por la variable de entorno `AFIP_ENV`.

## Ejemplo de uso

```python
from app.afip.wsaa import WSAAClient
from app.afip.wsfe import WSFEClient

# Autenticación
wsaa = WSAAClient(ambiente="homologacion")
token, sign = wsaa.login(cert_path="cert.crt", key_path="key.key")

# Emitir factura
wsfe = WSFEClient(ambiente="homologacion", token=token, sign=sign)
cae = wsfe.solicitar_cae(
    tipo_cbte=1,
    punto_vta=1,
    nro_cbte=123,
    ...
)
```

## Seguridad

- **NUNCA** loggear certificados o claves privadas
- Manejar certificados con permisos restrictivos (400)
- Validar fechas de vencimiento de certificados
- Rotar tokens regularmente (antes de expiración)
