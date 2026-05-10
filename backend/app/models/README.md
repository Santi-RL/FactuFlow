# Modelos SQLAlchemy

Esta carpeta contiene todos los modelos de base de datos usando SQLAlchemy ORM.

## Modelos Principales

### Empresa
Datos fiscales del emisor de comprobantes:
- CUIT (único)
- Razón social
- Domicilio fiscal
- Fecha de inicio de actividades
- Configuración de puntos de venta

### PuntoDeVenta
Puntos de venta habilitados en ARCA:
- Número de punto de venta
- Descripción/alias
- Sistema, domicilio y nombre fantasia importados desde constancia ARCA
- Estado Web Services, bloqueado, fecha de baja y usabilidad FactuFlow
- Relación con Empresa

### Certificado
Metadatos de certificados ARCA (NO el archivo):
- CUIT relacionado
- Alias del certificado
- Fechas de emisión y vencimiento
- Path del archivo en filesystem
- Ambiente (homologación/producción)
- Estado (activo/vencido/próximo a vencer)

### Cliente
Receptores de comprobantes:
- CUIT/CUIL/DNI
- Tipo de documento
- Nombre/Razón social
- Condición IVA
- Email (opcional)

### Comprobante
Facturas, Notas de Crédito, Notas de Débito:
- Tipo de comprobante
- Punto de venta y número
- Fecha de emisión
- CAE (Código de Autorización Electrónica)
- Totales (subtotal, IVA, total)
- Estado
- Snapshot fiscal del receptor al momento de emitir

### ComprobanteItem
Líneas de detalle de un comprobante:
- Descripción del producto/servicio
- Cantidad
- Precio unitario
- Alícuota de IVA
- Subtotal

### LoteComprobante, LoteComprobanteGrupo y LoteComprobanteFila
Emision masiva por Excel:
- Archivo, hash, estado y modo de procesamiento
- Formato de importacion usado, encabezados detectados y mapeo aplicado
- Grupos por `comprobante_ref`
- Filas originales del Excel con mensajes de validacion
- Contadores de grupos validos, emitidos y fallidos
- Datos para reanudar lotes grandes desde el worker

### FormatoImportacion, FormatoImportacionVersion, FormatoImportacionCampo y FormatoImportacionRegla
Formatos reutilizables para interpretar archivos externos de emision masiva:
- Alcance `global` o particular de una Empresa
- Version vigente con `configuracion_json`
- Campos destino con origen por encabezado, columna o constante
- Alias de encabezados, letras/indices de columna, transformaciones y valores
  default
- Reglas declarativas como agrupacion por fila
- Trazabilidad desde `LoteComprobante` hacia el formato y version usados

### PerfilCargaMasiva
Perfiles de carga masiva por emisor:
- Nombre unico dentro de cada Empresa
- Configuracion JSON versionada con formato opcional, concepto fiscal ARCA,
  descripcion facturada y reglas de fechas relativas
- Marca de predeterminado para precargar `Emision masiva`
- Trazabilidad desde `LoteComprobante.metadata_json` cuando un lote se valida
  con un perfil aplicado

## Convenciones

- Un modelo por archivo
- Nombres en español (Cliente, Empresa, Comprobante)
- Usar type hints
- Incluir docstrings
- Relaciones bien definidas con `relationship()`
- Índices en campos de búsqueda frecuente
