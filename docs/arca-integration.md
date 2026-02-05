# Integración con ARCA - Documentación

## Resumen

Se implementó la integración completa con los webservices de ARCA (Agencia de Recaudación y Control Aduanero, ex-AFIP) para emitir comprobantes electrónicos en Argentina.

## Componentes Implementados

### 1. Módulo Core (`backend/app/arca/`)

#### `config.py`
- Configuración de URLs de webservices según ambiente (homologación/producción)
- Clase `ArcaConfig` con properties para URLs de WSAA y WSFEv1

#### `exceptions.py`
- Excepciones personalizadas para errores de ARCA:
  - `ArcaError`: Excepción base
  - `ArcaAuthError`: Errores de autenticación
  - `ArcaValidationError`: Errores de validación
  - `ArcaConnectionError`: Errores de conexión
  - `ArcaServiceError`: Errores del servicio
  - `ArcaCertificateError`: Errores de certificados

#### `utils.py`
- Funciones de utilidad:
  - `format_cuit()`: Formatea CUIT al formato XX-XXXXXXXX-X
  - `validate_cuit()`: Valida CUIT con dígito verificador
  - `clean_cuit()`: Limpia CUIT removiendo caracteres no numéricos
  - `format_date_arca()`: Formatea fechas a YYYYMMDD
  - `parse_date_arca()`: Parsea fechas desde YYYYMMDD
  - `format_importe()`: Formatea importes con 2 decimales

#### `models.py`
- Modelos Pydantic para todas las requests y responses:
  - `TicketAcceso`: Token y sign del WSAA
  - `ComprobanteRequest`: Datos para solicitar CAE
  - `CAEResponse`: Respuesta con CAE autorizado
  - `TipoComprobante`, `TipoDocumento`, `TipoIva`, etc.: Parámetros de ARCA
  - `IvaItem`, `TributoItem`: Items de comprobantes

#### `crypto.py`
- Funciones de criptografía para certificados X.509:
  - `load_certificate()`: Carga certificado .crt
  - `load_private_key()`: Carga clave privada .key
  - `generate_tra()`: Genera TRA (Ticket de Requerimiento de Acceso) en XML
  - `sign_tra()`: Firma TRA con CMS/PKCS#7
  - `create_signed_tra()`: Crea y firma TRA en un paso
  - `verify_certificate_validity()`: Verifica que el certificado esté vigente

#### `cache.py`
- Sistema de cache en memoria para tokens de WSAA:
  - `TokenCache`: Clase para cachear tickets de acceso
  - Validación automática de expiración
  - Margen de seguridad de 5 minutos antes de expiración
  - Método `cleanup_expired()` para limpiar tokens vencidos

#### `wsaa.py`
- Cliente para Web Service de Autenticación y Autorización (WSAA):
  - `WSAAClient`: Cliente SOAP para WSAA
  - Método `login()`: Autentica y obtiene Token + Sign
  - Cache automático de tokens (12 horas de validez)
  - Manejo robusto de errores de autenticación

#### `wsfev1.py`
- Cliente para Web Service de Factura Electrónica v1 (WSFEv1):
  - `WSFEv1Client`: Cliente SOAP para WSFEv1
  - `fe_dummy()`: Test de disponibilidad del servicio
  - `fe_comp_ultimo_autorizado()`: Último número de comprobante
  - `fe_cae_solicitar()`: Solicita CAE para comprobante
  - `fe_comp_consultar()`: Consulta comprobante emitido
  - Métodos de parámetros:
    - `fe_param_get_tipos_cbte()`: Tipos de comprobante
    - `fe_param_get_tipos_doc()`: Tipos de documento
    - `fe_param_get_tipos_iva()`: Alícuotas de IVA
    - `fe_param_get_tipos_concepto()`: Tipos de concepto
    - `fe_param_get_tipos_monedas()`: Tipos de moneda
    - `fe_param_get_cotizacion()`: Cotización de moneda
    - `fe_param_get_ptos_venta()`: Puntos de venta habilitados

### 2. API REST (`backend/app/api/arca.py`)

Se crearon 11 endpoints RESTful para exponer la funcionalidad de ARCA:

#### Endpoints de Consulta
- `GET /api/arca/test-conexion`: Verifica conexión con ARCA usando FEDummy
- `GET /api/arca/tipos-comprobante`: Lista tipos de comprobante disponibles
- `GET /api/arca/tipos-documento`: Lista tipos de documento
- `GET /api/arca/tipos-iva`: Lista alícuotas de IVA
- `GET /api/arca/tipos-concepto`: Lista tipos de concepto
- `GET /api/arca/tipos-monedas`: Lista tipos de moneda
- `GET /api/arca/cotizacion/{moneda_id}`: Obtiene cotización de moneda
- `GET /api/arca/puntos-venta`: Lista puntos de venta habilitados
- `GET /api/arca/ultimo-comprobante/{pv}/{tipo}`: Último número autorizado

#### Endpoints de Operación
- `POST /api/arca/solicitar-cae`: Solicita CAE para un comprobante
- `GET /api/arca/consultar-comprobante/{pv}/{tipo}/{num}`: Consulta comprobante

#### Autenticación y Seguridad
- Todos los endpoints requieren autenticación (usuario empresa)
- Obtención automática de certificado activo de la empresa
- Autenticación transparente con WSAA
- Manejo de errores HTTP apropiados (401, 403, 404, 422, 500, 503)

### 3. Tests (`backend/tests/test_arca/`)

Se crearon 42 tests unitarios y de integración:

#### `test_utils.py` (24 tests)
- Tests de formateo y validación de CUIT
- Tests de formateo de fechas
- Tests de formateo de importes

#### `test_crypto.py` (6 tests)
- Tests de generación de TRA
- Tests de carga de certificados
- Tests de manejo de errores

#### `test_cache.py` (8 tests)
- Tests de set/get de tokens
- Tests de expiración de tokens
- Tests de limpieza de cache

#### `test_arca_api.py` (4 tests)
- Tests de endpoints con mocks
- Tests de autenticación
- Tests de respuestas

**Resultado: 42/42 tests pasando ✅**

### 4. Dependencias

Se agregó a `requirements.txt`:
- `lxml==5.1.0`: Parseo XML (requerido por zeep)

Dependencias ya existentes:
- `zeep==4.2.1`: Cliente SOAP
- `cryptography==42.0.4`: Firma de certificados

## Configuración

### Variables de Entorno

Las siguientes variables ya existen en `.env.example`:

```bash
# Ambiente de ARCA: "homologacion" o "produccion"
AFIP_ENV=homologacion

# Ruta donde se almacenan los certificados
AFIP_CERTS_PATH=./certs
```

También se aceptan:
- `ARCA_ENV` (alternativa a `AFIP_ENV`)
- `ARCA_CERTS_PATH` (alternativa a `AFIP_CERTS_PATH`)

### Certificados

Los certificados deben estar en la carpeta configurada (`./certs` por defecto):
- `certificado.crt`: Certificado X.509
- `certificado.key`: Clave privada

**Importante**: Los archivos de certificados NO deben commitearse a Git (ya están en `.gitignore`).

## Flujo de Uso

### 1. Autenticación

El sistema maneja automáticamente la autenticación:

1. El usuario hace un request a cualquier endpoint de ARCA
2. El sistema busca el certificado activo de la empresa
3. Se autentica con WSAA usando el certificado
4. Se obtiene Token y Sign (válidos por 12 horas)
5. El token se cachea para reutilización
6. Se crea cliente WSFEv1 con las credenciales

### 2. Emisión de Comprobante

```python
# POST /api/arca/solicitar-cae
{
  "punto_venta": 1,
  "tipo_cbte": 6,  # Factura B
  "concepto": 1,   # Productos
  "tipo_doc": 80,  # CUIT
  "nro_doc": 20123456789,
  "cbte_desde": 1,
  "cbte_hasta": 1,
  "fecha_cbte": "20241231",
  "imp_total": 1210.00,
  "imp_neto": 1000.00,
  "imp_iva": 210.00,
  "imp_op_ex": 0,
  "imp_tot_conc": 0,
  "imp_trib": 0,
  "moneda_id": "PES",
  "moneda_cotiz": 1,
  "iva": [
    {
      "id": 5,        # 21%
      "base_imp": 1000.00,
      "importe": 210.00
    }
  ]
}
```

### 3. Respuesta CAE

```json
{
  "cae": "12345678901234",
  "cae_vencimiento": "20250107",
  "numero_comprobante": 1,
  "tipo_cbte": 6,
  "punto_venta": 1,
  "resultado": "A",
  "observaciones": [],
  "errores": []
}
```

## URLs de ARCA

### Homologación (Testing)
- WSAA: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- CUIT de prueba: `20409378472`

### Producción
- WSAA: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

**Nota**: Las URLs mantienen "afip.gov.ar" por razones técnicas y de compatibilidad, aunque el organismo ahora se llama ARCA.

## Manejo de Errores

### Errores de ARCA

El sistema traduce los códigos de error de ARCA a mensajes en español:

- `ArcaAuthError` (401): Error de autenticación
- `ArcaValidationError` (422): Error de validación de datos
- `ArcaConnectionError` (503): Error de conexión con ARCA
- `ArcaServiceError` (500): Error del servicio

### Errores de Certificados

- Certificado vencido
- Certificado no válido aún
- Archivo de certificado no encontrado
- Error al cargar clave privada

## Logging

Se utiliza el módulo `logging` de Python:

```python
import logging
logger = logging.getLogger(__name__)
```

Los logs incluyen:
- Solicitudes de autenticación
- Tokens obtenidos y expiración
- Errores de SOAP
- Errores de servicio

## Próximos Pasos

Para completar la integración:

1. **Crear wizard de configuración de certificados** en el frontend
2. **Integrar con modelo Comprobante** para guardar CAE en BD
3. **Agregar validaciones adicionales** (ej: verificar que punto de venta esté habilitado)
4. **Implementar reintento automático** en caso de errores transitorios
5. **Agregar soporte para otros webservices** (WSFEx, etc.)

## Documentación Adicional

- [Documentación oficial ARCA WS](https://www.arca.gob.ar/ws/)
- [Documentación oficial ARCA](https://www.arca.gob.ar/)
- [Especificación WSAA](https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.0.pdf)
- [Especificación WSFEv1](https://www.afip.gob.ar/ws/WSFEV1/WSFEV1-especificacion.pdf)
