# Manual de Usuario - FactuFlow

Guía completa para usar FactuFlow y emitir facturas electrónicas.

## Contenido

1. [Configuración Inicial](#configuración-inicial)
2. [Gestión de Clientes](#gestión-de-clientes)
3. [Emisión de Facturas](#emisión-de-facturas)
4. [Consulta de Comprobantes](#consulta-de-comprobantes)
5. [Reportes](#reportes)
6. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## Configuración Inicial

### Primer Acceso

1. **Acceder a FactuFlow**
   - Abrir navegador en http://localhost:8080
   - O tu dominio si está en producción

2. **Login**
   - Usuario: `admin` (por defecto)
   - Password: La que configuraste durante la instalación

3. **Configurar tu Empresa**
   - Ir a "Configuración" en el menú
   - Completar:
     - CUIT de tu empresa
     - Razón social
     - Domicilio fiscal
     - Fecha de inicio de actividades
     - Puntos de venta habilitados en AFIP

4. **Configurar Certificado AFIP**
   - Ir a "Certificados" en el menú
   - Seguir el [Wizard de Certificados](../certificates/README.md)
   - **Importante**: Empezar con ambiente de **Homologación** para pruebas

---

## Gestión de Clientes

### Crear un Nuevo Cliente

1. **Ir a "Clientes"** en el menú lateral

2. **Click en "Nuevo Cliente"**

3. **Completar el Formulario:**
   - **CUIT/CUIL/DNI**: Número de documento del cliente
     - FactuFlow validará automáticamente el formato
   - **Tipo de Documento**: CUIT, CUIL, DNI, Pasaporte, etc.
   - **Nombre/Razón Social**: Nombre completo o razón social
   - **Condición IVA**:
     - Responsable Inscripto
     - Monotributista
     - Consumidor Final
     - Exento
   - **Email** (opcional): Para enviar facturas automáticamente
   - **Domicilio** (opcional): Dirección del cliente

4. **Click en "Guardar"**

### Editar Cliente

1. Ir a "Clientes"
2. Click en el ícono de lápiz (✏️) junto al cliente
3. Modificar los datos necesarios
4. Click en "Guardar"

### Buscar Cliente

- Usar la barra de búsqueda en la parte superior
- Podés buscar por nombre o CUIT
- Los resultados se filtran automáticamente

---

## Emisión de Facturas

### Nueva Factura - Paso a Paso

#### Paso 1: Tipo de Comprobante

1. **Click en "Nueva Factura"** en el menú o en la página de Comprobantes

2. **Seleccionar Tipo:**
   - **Factura A**: Para clientes Responsables Inscriptos
     - Discrimina IVA
     - Requiere CUIT del cliente
   - **Factura B**: Para Consumidores Finales y Monotributistas
     - IVA incluido
     - Puede ser DNI o CUIT
   - **Factura C**: Para operaciones exentas
     - Sin IVA

3. **Seleccionar Punto de Venta**
   - Dropdown con tus puntos de venta habilitados
   - El número de comprobante se asignará automáticamente

#### Paso 2: Seleccionar Cliente

1. **Buscar Cliente Existente:**
   - Escribir nombre o CUIT en el buscador
   - Seleccionar de la lista

2. **O Crear Cliente Rápido:**
   - Click en "Nuevo Cliente"
   - Completar datos mínimos:
     - CUIT/DNI
     - Nombre
     - Condición IVA
   - Se guardará automáticamente

#### Paso 3: Agregar Items

1. **Click en "Agregar Item"**

2. **Completar Datos del Item:**
   - **Descripción**: Qué estás facturando
     - Ej: "Servicios de consultoría - Enero 2024"
     - Ej: "Producto XYZ - Código 123"
   - **Cantidad**: Número de unidades
   - **Precio Unitario**: Precio sin IVA (en Factura A)
   - **IVA**: Seleccionar alícuota
     - 0% (exento)
     - 10.5%
     - 21% (más común)
     - 27%

3. **Ver Subtotal Calculado**
   - Se calcula automáticamente: Cantidad × Precio × (1 + IVA)

4. **Agregar más items** si es necesario
   - Click en "Agregar Item" nuevamente
   - Repetir proceso

5. **Verificar Totales**
   - **Subtotal**: Suma de todos los items sin IVA
   - **IVA**: Desglosado por alícuota
   - **Total**: Importe final a pagar

#### Paso 4: Vista Previa

1. **Click en "Vista Previa"**

2. **Revisar Todos los Datos:**
   - Tipo y número de comprobante
   - Datos del cliente
   - Items y totales
   - Todo debe ser correcto antes de emitir

3. **Si hay errores:**
   - Click en "Volver a Editar"
   - Corregir los datos

#### Paso 5: Emitir

1. **Click en "Emitir Comprobante"**

2. **Esperar Respuesta de AFIP**
   - Se mostrará un spinner
   - Puede tardar 5-10 segundos

3. **Resultado:**

   **✅ Éxito: CAE Otorgado**
   - Se mostrará modal con:
     - CAE (Código de Autorización Electrónica)
     - Vencimiento del CAE
     - Opciones:
       - Ver Comprobante
       - Imprimir PDF
       - Enviar por Email

   **❌ Error: Comprobante Rechazado**
   - AFIP mostrará el motivo del rechazo
   - Ejemplos:
     - "CUIT inexistente"
     - "Punto de venta no habilitado"
     - "Error en cálculo de IVA"
   - Corregir y volver a intentar

---

## Consulta de Comprobantes

### Listado de Comprobantes

1. **Ir a "Comprobantes"** en el menú

2. **Ver Listado Completo:**
   - Tipo de comprobante (badge con color)
   - Número (formato: 0001-00000123)
   - Fecha
   - Cliente
   - Total
   - CAE
   - Estado (Autorizado/Rechazado)

3. **Filtrar:**
   - Por tipo de comprobante
   - Por rango de fechas
   - Por cliente
   - Por estado

4. **Ordenar:**
   - Click en encabezados de columna
   - Ordenar por fecha, número, total, etc.

### Ver Detalle de Comprobante

1. Click en el ícono de ojo (👁️) o en el número del comprobante

2. **Ver Información Completa:**
   - Todos los datos del comprobante
   - Items detallados
   - CAE y vencimiento
   - Código QR (según normativa AFIP)

3. **Acciones Disponibles:**
   - **Imprimir**: Genera y abre PDF
   - **Descargar PDF**: Descarga archivo
   - **Enviar por Email**: Abre modal para enviar
   - **Reimprimir**: Para comprobantes antiguos

### Descargar PDF

El PDF incluye:
- Logo de tu empresa
- Datos fiscales completos
- Tipo de comprobante destacado (A, B, C)
- Número de comprobante
- CAE y vencimiento CAE
- Datos del cliente
- Tabla de items
- Totales desglosados
- Código QR según normativa AFIP
- Leyendas legales

---

## Reportes

### Ventas por Período

1. **Ir a "Reportes" → "Ventas"**

2. **Seleccionar Período:**
   - Rango de fechas personalizado
   - O presets: Esta semana, Este mes, Este año

3. **Ver Reporte:**
   - Gráfico de ventas (barras o líneas)
   - Total facturado
   - Cantidad de comprobantes
   - Promedio por comprobante

4. **Exportar:**
   - Excel (.xlsx)
   - CSV
   - PDF

### IVA Ventas

1. **Ir a "Reportes" → "IVA Ventas"**

2. **Seleccionar Mes**

3. **Ver Libro IVA:**
   - Listado de todos los comprobantes
   - Desglose de IVA por alícuota
   - Totales para DDJJ

4. **Exportar** para cargar en libro IVA digital

---

## Preguntas Frecuentes

### ¿Puedo emitir facturas sin conexión a internet?

No. FactuFlow necesita conexión para comunicarse con AFIP en tiempo real y obtener el CAE.

### ¿Puedo anular una factura?

Las facturas electrónicas no se anulan, se emite una **Nota de Crédito** que cancela el comprobante original.

### ¿Qué pasa si AFIP está en mantenimiento?

FactuFlow mostrará un error. Intentá más tarde. Podés guardar como borrador para no perder los datos.

### ¿Puedo emitir múltiples facturas a la vez?

No, cada factura debe emitirse individualmente y obtener su CAE de AFIP.

### ¿Los comprobantes de homologación son válidos?

No. Son solo para pruebas. Para facturación real, debés usar ambiente de **Producción**.

### ¿Cómo paso de homologación a producción?

1. Obtener certificado de producción desde AFIP
2. Subirlo a FactuFlow
3. Cambiar `AFIP_ENV=produccion` en configuración
4. Reiniciar FactuFlow

⚠️ **Solo hacerlo cuando estés seguro de que todo funciona correctamente.**

### ¿Puedo facturar en dólares u otras monedas?

Sí, AFIP soporta múltiples monedas. FactuFlow lo implementará en futuras versiones.

### ¿Qué es el CAE?

**CAE** = Código de Autorización Electrónica. Es el número que AFIP asigna a tu factura para validarla. Sin CAE, la factura no es válida.

### ¿Cuánto tiempo tengo para imprimir/enviar la factura después de obtener el CAE?

El CAE tiene un vencimiento (generalmente 10 días). Debés entregar el comprobante al cliente antes de ese vencimiento.

### ¿Puedo usar FactuFlow para múltiples empresas?

Actualmente, cada instalación de FactuFlow es para una empresa (un CUIT). Para múltiples empresas, instalá múltiples instancias.

---

## Soporte

¿Necesitás ayuda?

- 📖 [Guía de Certificados](../certificates/README.md)
- 📖 [Guía de Instalación](../setup/README.md)
- 💬 [GitHub Discussions](https://github.com/Santi-RL/FactuFlow/discussions)
- 🐛 [Reportar Bug](https://github.com/Santi-RL/FactuFlow/issues)

---

**¡Feliz Facturación! 📄✨**
