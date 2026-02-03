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

### ComprobanteItem
Líneas de detalle de un comprobante:
- Descripción del producto/servicio
- Cantidad
- Precio unitario
- Alícuota de IVA
- Subtotal

## Convenciones

- Un modelo por archivo
- Nombres en español (Cliente, Empresa, Comprobante)
- Usar type hints
- Incluir docstrings
- Relaciones bien definidas con `relationship()`
- Índices en campos de búsqueda frecuente
