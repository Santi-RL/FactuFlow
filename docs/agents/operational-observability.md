# Observabilidad operativa estandar

Estado: decision vigente desde 2026-05-22.

## Objetivo

FactuFlow ya fue usado en produccion real. Antes de ampliar el uso productivo,
el sistema debe poder explicar que paso en una operacion importante sin depender
de memoria manual ni de revisar la base a ciegas.

Esta etapa no busca monitoreo complejo. Busca diagnostico operativo claro,
simple y accionable para usuarios administrativos, soporte y desarrollo.

## Principio de producto

- Los mensajes deben estar escritos para usuarios no tecnicos.
- Si algo falla, la pantalla debe explicar que paso, que impacto tiene y cual
  es el proximo paso seguro.
- No mostrar opciones tecnicas sin explicacion.
- No usar terminos internos como unica respuesta. Si aparece un dato tecnico,
  debe tener una descripcion simple.
- No mezclar datos entre emisores. Todo diagnostico debe indicar o respetar el
  emisor activo correspondiente.
- No copiar CUITs, CAEs, datos de clientes, Excels, PDFs ni logs privados en
  documentacion versionada.

## Alcance obligatorio

### 1. Registro claro de operaciones criticas

Cada operacion importante debe dejar una pista suficiente para reconstruir que
ocurrio:

- usuario que inicio la accion
- emisor activo usado
- lote, comprobante o recurso afectado
- punto de venta cuando aplique
- fecha fiscal cuando aplique
- estado inicial y estado final
- si el error ocurrio antes de llamar a ARCA, durante la llamada o despues de
  una respuesta de ARCA
- codigo o identificador de seguimiento para soporte

### 2. Trazabilidad visible de lotes

Los lotes deben mostrar estados entendibles:

- pendiente
- en cola
- procesando
- completado
- completado parcial
- fallido
- requiere reconciliacion

Cuando un lote quede en error, el usuario debe poder entender si puede corregir
el archivo, reintentar, esperar al worker o pedir soporte. Si existe
incertidumbre despues de ARCA, no debe sugerirse un reintento automatico sin
reconciliacion.

### 3. Estado del sistema en la interfaz

Debe existir una pantalla o panel de `Estado del sistema` con lenguaje simple.
Como minimo debe informar:

- aplicacion backend disponible
- base de datos disponible
- worker de lotes disponible
- conexion ARCA segun ambiente
- certificado activo del emisor seleccionado
- vencimiento o problema visible del certificado
- uso de almacenamiento de la instalación, con desglose por emisor y tipo de
  dato, cuando el usuario sea administrador
- ubicacion o acceso a logs relevantes cuando sea seguro
- ultimo backup conocido o aviso de backup no verificado, cuando esa evidencia
  exista

Los estados visibles deben usar etiquetas simples como `Correcto`,
`Necesita atencion` y `No disponible`, con una explicacion corta.

La primera vista administrativa de esta línea ya existe en
`Sistema > Almacenamiento`: muestra uso medido, recuperable, límite
configurado, espacio libre de disco, categorías y uso por emisor, y permite
resguardar/descargar antes de liberar artefactos no vitales.

### 4. Backups y restauracion probados

Antes de ampliar volumen productivo, debe existir un procedimiento probado para:

- backup de PostgreSQL
- backup de certificados y claves
- backup de configuracion productiva
- restauracion en entorno controlado
- verificacion posterior de que la aplicacion levanta y puede consultar datos

La documentacion debe explicar el procedimiento paso a paso y con advertencias
claras sobre datos privados.

### 5. Logs utiles para soporte

Los logs deben servir para diagnosticar sin exponer datos privados en el repo.
Deben permitir correlacionar una operacion con:

- emisor interno
- usuario interno
- lote o comprobante
- job o worker involucrado
- error local o error ARCA

Los logs privados quedan fuera de Git. La documentacion versionada solo debe
describir donde se generan y como usarlos de forma segura.

### 6. Runbook de diagnostico

Debe existir una guia de soporte con casos comunes:

- la aplicacion no inicia
- no se puede iniciar sesion
- ARCA no responde
- certificado vencido o no autorizado
- lote trabado o parcial
- comprobante con incertidumbre post-ARCA
- backup o restauracion requerida

Cada caso debe indicar pasos concretos, en orden, y cuando detenerse para evitar
acciones fiscales riesgosas.

## Fuera de alcance por ahora

Estas herramientas pueden venir despues, pero no son requisito de esta etapa:

- Grafana, Prometheus o dashboards tecnicos avanzados
- alertas automaticas externas
- monitoreo distribuido
- trazas distribuidas
- centralizacion completa de logs

## Criterio de completado

La observabilidad operativa estandar queda lista cuando una persona de soporte o
un usuario administrativo puede responder, desde la interfaz y la documentacion:

1. Que emisor estaba activo.
2. Que lote o comprobante se intento operar.
3. Que estado tiene ahora.
4. Si ARCA fue llamada o no.
5. Si hay incertidumbre fiscal o no.
6. Donde mirar el detalle seguro.
7. Que accion corresponde hacer ahora.
