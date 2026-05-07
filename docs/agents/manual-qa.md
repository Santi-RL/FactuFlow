# QA manual

Ultima actualizacion: 2026-05-05

Este archivo registra el avance real de la prueba manual de la interfaz. Si una sesion queda a mitad de camino, se retoma desde aca.

## Preparacion

Levantar el proyecto:

```bash
powershell -ExecutionPolicy Bypass -File .\run-local.ps1
```

Entornos esperados:
- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

## Acceso local usado

Solo para entorno local de desarrollo:
- Usuario QA automatizable: `visual@factuflow.dev`
- Contrasena QA local: `admin123`

Para crear o promover un usuario propietario local, usar:

```bash
cd backend
.venv\Scripts\python.exe -m app.scripts.create_admin_user
```

Si deja de funcionar, validar la base local o resetear la clave con el mismo comando.

## Recorrido ejecutado y validado

### 1. Dashboard

- Cargo correctamente.
- El selector de empresa activa se vio bien.
- Se corrigieron los KPIs hardcodeados.
- Estado validado hoy:
  - `Total Clientes = 7`
  - `Comprobantes del Mes = 3`
  - `Ultimo Comprobante = 0005-00000006`
  - `Estado Certificado = Valido`

### 2. Comprobantes

- El listado mostro correctamente 6 comprobantes autorizados.
- Se verificaron columnas tipo, numero, fecha, cliente, total, estado y acciones.

### 3. Detalle de comprobante

- El detalle carga correctamente.
- Se verificaron CAE, vencimiento, cliente, items y totales.

### 4. PDF

- `Ver PDF` abre correctamente.
- Se visualizo CAE y QR.
- `Descargar PDF` descarga correctamente el archivo.

### 5. Nueva factura

- Se completo el flujo real desde UI.
- Se detecto y corrigio un fallo en `proximo-numero` causado por resolucion incorrecta del path de certificados legacy.
- Resultado real:
  - `Factura B`
  - `0005-00000004`
  - CAE `86150042970986`

### 6. Emision masiva

- `Descargar plantilla` funciona.
- La validacion del lote funciona.
- La emision del lote funciona desde UI.
- `Descargar observado` funciona sobre el lote completado.
- Se valido desde UI un lote productivo preparatorio con consumidor final sin
  documento (`qa_lote_cf_sin_documento.xlsx`) para el emisor real. Resultado:
  `Validado`, `Listos para emitir = 1`, receptor `A CONSUMIDOR FINAL`,
  documento `0`, punto de venta `6`, total estimado `$1.210,00`. No se presiono
  `Emitir comprobantes validos`.
- Resultado real:
  - `0005-00000005` -> CAE `86150042971165`
  - `0005-00000006` -> CAE `86150042971178`

### 7. Clientes

- El listado carga correctamente.
- En el flujo legacy de homologacion se verifico que los clientes creados automaticamente por emision masiva quedaron visibles:
  - `Consumidor Final Lote Uno`
  - `Consumidor Final Lote Dos`
- Desde 2026-05-05, los lotes masivos no crean clientes persistentes por defecto
  cuando el receptor viene solo como consumidor final del Excel; el comprobante
  guarda snapshot fiscal del receptor.

### 8. Reportes

- `Ventas por periodo` carga y muestra los 3 comprobantes de abril.
- `IVA ventas` carga y refleja bases e IVA de abril.
- `Ranking de clientes` carga y ordena correctamente los clientes facturados.

### 9. Certificados

- La vista carga correctamente.
- Se visualizo certificado homologacion valido, ambiente y vencimiento.
- Se agrego accion `Probar conexion` en cada certificado para validar WSAA/ARCA
  antes de emitir, reutilizando el endpoint scopiado por emisor activo.
- Se agrego al wizard el paso previo de autorizar `wsfe` en ARCA antes de
  ejecutar `Probar conexion`.

### 10. Puntos de venta

- La vista carga correctamente.
- Se verifico el punto de venta `0005` activo.
- Durante la QA se detecto y corrigio un fallo real en `Sincronizar con ARCA`.
- Estado final: sincronizacion ejecutada con respuesta OK desde UI.
- En preparacion productiva se sincronizaron para el emisor real los puntos
  habilitados `6`, `8`, `10`, `12`, `13` y `14`; ARCA devolvio `7` y `9`
  bloqueados.
- Se importo la constancia PDF de puntos de venta del CUIT real y se valido que
  quedan visibles sistema, domicilio, nombre fantasia, usabilidad FactuFlow y
  estado bloqueado/no bloqueado.

### 11. Mi Empresa

- La pantalla dejo de estar en placeholder.
- Se implemento formulario real contra la API.
- Se probo guardado desde UI con `PUT 200`.

## Hallazgos corregidos durante la QA

- Detalle de comprobante: faltaba `result.unique()`.
- Preview de PDF: el frontend llamaba mal la ruta.
- Proximo numero para nueva factura: path legacy de certificado mal resuelto.
- Sincronizacion de puntos de venta ARCA: helper usaba el CUIT incorrecto.
- Dashboard: KPIs hardcodeados.
- Mi Empresa: placeholder sin funcionalidad.

## Resultado

- QA manual funcional cerrada para el alcance actual del MVP en homologacion.
- El flujo de emision masiva ahora distingue lotes chicos sincronos y lotes grandes en cola.
- La pantalla muestra estado `En cola` para lotes grandes y continua haciendo polling hasta `Procesando`/resultado final.
- La pantalla `Emisores` permite agregar un nuevo emisor desde un modal y
  seleccionarlo como activo al crearlo.
- En el modal `Agregar emisor`, la accion `Subir constancia` procesa un PDF de
  constancia ARCA y precompleta los datos detectados sin guardar automaticamente.
- Puntos de venta respeta el emisor activo: al seleccionar un emisor nuevo sin
  puntos cargados, no muestra puntos de otros emisores.
- Quedan pendientes las tareas externas de salida a produccion que no se resuelven desde esta QA local.

## Punto de reanudacion

Retomar en la preparacion de produccion:

1. Certificado productivo.
2. Autorizacion `wsfe` productiva.
3. Punto de venta productivo.
4. Levantar perfil productivo con PostgreSQL usando `docker-compose.prod.yml`.
5. Checklist operativo de go-live y backup.
