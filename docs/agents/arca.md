# Integracion ARCA

## Nomenclatura

- ARCA es el nombre actual y debe usarse en UI, documentacion nueva y textos de soporte.
- AFIP sigue apareciendo en URLs oficiales y nombres legacy por compatibilidad tecnica.

## Modulos relevantes

- `backend/app/arca/wsaa.py`: autenticacion WSAA
- `backend/app/arca/wsfev1.py`: integracion WSFEv1
- `backend/app/arca/crypto.py`: firmado y utilidades criptograficas
- `backend/app/arca/cache.py`: cache de tickets WSAA
- `backend/app/arca/models.py`: modelos de request/response
- `backend/app/services/facturacion_service.py`: orquestacion de emision real
- `backend/app/api/arca.py`: endpoints HTTP vinculados a ARCA

## Endpoints oficiales

- WSAA homologacion: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSAA produccion: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1 homologacion: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- WSFEv1 produccion: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`

## Variables de entorno reales del proyecto

- `ARCA_ENV`: `homologacion` o `produccion`
- `CERTS_PATH`: base path de certificados
- `ARCA_TOKEN_CACHE_PATH`: cache persistente de tickets WSAA
- En produccion, usar PostgreSQL y `docker-compose.prod.yml`; no usar SQLite ni defaults de desarrollo.
- Compatibilidad legacy:
  - `AFIP_ENV`
  - `AFIP_CERTS_PATH`

## Hallazgos importantes de homologacion

### Certificados y WSASS

- En homologacion se trabajo con WSASS.
- El certificado se emitio para el CUIT del titular del certificado y luego se autorizo el servicio `wsfe` para el CUIT representado.
- Flujo confirmado:
  1. Adherir `WSASS - Autogestion Certificados Homologacion`
  2. Generar CSR con el CUIT del titular del certificado
  3. Crear DN/certificado en WSASS
  4. Crear autorizacion al servicio `wsfe` para el CUIT representado

### Certificados en produccion

- En produccion no alcanza con cargar el certificado emitido por ARCA.
- Despues de generar el certificado en `Administracion de Certificados Digitales`,
  el administrador/representante debe asociar el alias del computador al servicio
  `wsfe` desde `Administrador de Relaciones de Clave Fiscal`.
- Si falta esa autorizacion, WSAA responde `Computador no autorizado a acceder
  al servicio`, aunque el certificado y la clave privada coincidan.
- El wizard de FactuFlow tiene un paso previo a `Probar conexion` para confirmar
  esta asociacion.

### CUIT operativo para WSFE

- En el runtime del proyecto no debe reutilizarse automaticamente el `cuit` del certificado para operar WSFE.
- El flujo correcto validado hoy es:
  - resolver certificado activo
  - autenticar WSAA para la empresa activa representada
  - construir `WSFEv1Client` con el CUIT de la empresa activa
- Este ajuste fue necesario para corregir `GET /api/arca/puntos-venta`, que fallaba aunque la emision real funcionaba.

### Paths legacy de certificados

- La base local puede contener valores legacy como `certs/archivo.crt`.
- El proyecto ahora resuelve correctamente:
  - paths absolutos
  - filenames simples
  - valores legacy con prefijo `certs/`
- Este fix fue necesario para que `Nueva factura` volviera a obtener el proximo numero desde homologacion.

### Puntos de venta

- No se detecto una pantalla separada en el portal que diga "homologacion" para los puntos de venta de WSFEv1.
- En la practica se revisa la misma pantalla `A/B/M de puntos de venta / emision`.
- Para webservices, el indicio util es la columna `Sistema`, por ejemplo `RECE para aplicativo y web services`.
- En esta sesion se uso el punto de venta `5`.
- En produccion para `FUNDACION ESCUELA DE GIMNASIA FEDE MOLINARI`, ARCA
  devolvio habilitados `6`, `8`, `10`, `12`, `13` y `14`; `7` y `9` estaban
  bloqueados.
- `FEParamGetPtosVenta` no devuelve domicilio ni nombre fantasia. Esos datos se
  importan desde la constancia PDF de `Administracion de Puntos de Venta y
  Domicilios`.
- La constancia permite ver tambien puntos de otros sistemas como Factuweb,
  Comprobantes en Linea y Controlador Fiscal; deben mostrarse pero no tratarse
  como usables para FactuFlow si no son Web Services.

### TLS en endpoints legacy

- El WSDL productivo de WSFEv1 puede fallar en Python/OpenSSL moderno con
  `DH_KEY_TOO_SMALL`.
- El cliente SOAP usa un transporte propio con `DEFAULT:@SECLEVEL=1`, limitado
  a llamadas ARCA, para mantener compatibilidad con esos endpoints.

### Verificacion de comprobantes

- La forma confiable de verificar comprobantes de homologacion es `FECompConsultar`.
- El QR sirve para comprobantes reales, pero no se tomo como mecanismo de validacion de homologacion.

### Particularidades observadas en homologacion

- `FEParamGetPtosVenta` puede devolver error `602 - Sin Resultados` aun cuando `FECompUltimoAutorizado` y la emision real funcionen.
- El codigo actual tolera ese caso solo en homologacion y no bloquea la emision si el resto de las validaciones da bien.
- En la QA del 2026-04-10 tambien se verifico que la sincronizacion de puntos de venta desde UI ya no usa el CUIT incorrecto.

### RG 5616 / Condicion frente al IVA del receptor

- En homologacion ARCA exigio `CondicionIVAReceptorId`.
- Mapping implementado:
  - `RI` -> `1`
  - `Monotributo` -> `6`
  - `Exento` -> `4`
  - `CF` -> `5`

### Consumidor final e identificacion del receptor

- La pagina publica de ARCA sobre comprobantes indica que, para receptor
  consumidor final, debe figurar la leyenda `A CONSUMIDOR FINAL`.
- Tambien indica que la identificacion con CUIT/CUIL/CDI/DNI u otro documento es
  obligatoria cuando el importe de la operacion es igual o superior a
  `$10.000.000`.
- FactuFlow aplica esto en emision masiva para comprobantes B/C:
  - bajo ese umbral acepta documento y nombre vacios desde Excel
  - normaliza a tipo documento `99`, numero `0`, razon social
    `A CONSUMIDOR FINAL` y condicion IVA `CF`
  - desde ese umbral exige documento
- Para comprobantes tipo A se mantiene obligatorio CUIT valido del receptor.

## Hallazgos tecnicos de integracion solucionados

- Cache WSAA antes solo en memoria; ahora persiste en `backend/data/arca_token_cache.json`.
- `FECAESolicitar` debia enviar:
  - `FeDetReq: { FECAEDetRequest: [...] }`
  - `Iva: { AlicIva: [...] }`
  - `Tributos: { Tributo: [...] }`
- El proyecto ya contempla esas estructuras correctas.
- La numeracion de comprobantes ahora se protege con:
  - lock en memoria por empresa/punto de venta/tipo
  - advisory lock transaccional si la base es PostgreSQL
  - constraint unico local por empresa/punto de venta/tipo/numero
- Para una prueba real, sigue siendo obligatorio confirmar punto de venta productivo y numeracion correlativa en ARCA antes del primer CAE.

## Smoke real completado el 2026-03-09

- Certificado homologacion emitido y autorizado por WSASS.
- Emision individual real OK.
- Emision masiva real OK.
- PDF de comprobante homologado generado.

Los CAEs emitidos en la sesion estan documentados en `docs/project/notes/SESSION_2026-03-09.md`.

## QA real completada el 2026-04-10

- `Ver PDF` y `Descargar PDF` revalidados manualmente.
- Emision individual real desde UI:
  - `0005-00000004`
  - CAE `86150042970986`
- Emision masiva real desde UI:
  - `0005-00000005`
  - CAE `86150042971165`
  - `0005-00000006`
  - CAE `86150042971178`
- `Sincronizar con ARCA` en puntos de venta corregido y revalidado manualmente.

## Referencias locales

- Curacion documental: `docs/arca-ws/README.md`
- Notas practicas: `docs/arca-ws/NOTAS.md`
