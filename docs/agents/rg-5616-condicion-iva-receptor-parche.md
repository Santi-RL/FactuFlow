# RG 5616 — parche de condición IVA del receptor

Fecha: 08/09/2026. Estado: alcance aceptado; implementación pendiente.

## Objetivo y prioridad

Garantizar que toda nueva solicitud de autorización de los comprobantes ya
soportados envíe `CondicionIVAReceptorId` presente, válido y compatible con su
clase. Es un parche P1 de seguridad fiscal y continuidad operativa, a continuación
del parche de emisión parcial y reintentos según el orden de
[ROADMAP.md](../../ROADMAP.md). No acredita un incidente productivo ni el
cumplimiento de una instalación hasta su verificación autorizada.

El código ya mapea RI, Monotributo, Exento y CF, pero permite omitir el campo
cuando el mapeo no reconoce el valor. Además, ofrece «Responsable No Inscripto»
y lo convierte en RI. El aviso recibido anuncia rechazo por ausencia del dato
desde el 01/12/2026. Su evidencia permanece privada; esa fecha no compromete una
release ni posterga la corrección del contrato fiscal.

Fuentes: [RG 5616/2024, artículo 2](https://www.argentina.gob.ar/normativa/nacional/norma-407369/texto)
y [manual oficial WSFEv1](https://www.afip.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
campo `CondicionIVAReceptorId`, validaciones 10242/10243/10246 y catálogo
`FEParamGetCondicionIvaReceptor`. Verificar la matriz vigente antes de codificar.

## Alcance cerrado

- Completar la validación y el envío en los caminos actuales de emisión
  individual y masiva, incluidos API, worker y reintentos que generen una nueva
  solicitud. Reutilizar una regla compartida; PF-13 la consumirá posteriormente.
- Aceptar las condiciones soportadas y sus equivalencias inequívocas. Un dato
  vacío, desconocido o incompatible debe producir un error comprensible antes
  de solicitar CAE; nunca completar el requisito inventando una condición.
- Resolver la opción «Responsable No Inscripto» sin convertirla silenciosamente
  en RI ni en otra categoría. Los valores ambiguos requieren corrección explícita
  para nuevas emisiones; no se reclasifican registros históricos.
- Ajustar sólo los controles y mensajes necesarios para corregir ese dato en
  los flujos existentes. Conservar archivos homogéneos y valores fijos válidos,
  sin exigir columnas adicionales cuando la condición ya esté resuelta.

Quedan fuera: rediseño de pantallas o constructor, nuevos regímenes o categorías,
consultas de padrón por factura, sincronizaciones periódicas, refactor general,
otras reglas fiscales y reconstrucción o corrección masiva de historia. No se
añaden confirmaciones rutinarias. Si aparece otro problema, se informa aparte.

## Compatibilidad y aceptación

Antes de implementar, completar el [checklist fiscal](fiscal-change-checklist.md)
con los consumidores afectados y aplicar [calidad Nivel 2](change-quality-gates.md).
El tamaño acotado del parche no reduce sus garantías de emisión.

| Caso | Resultado exigido |
|---|---|
| Condición soportada y compatible | Código correcto presente en cada detalle enviado, también en comprobantes C y lotes. |
| Dato vacío, desconocido, ambiguo o incompatible | Error accionable antes de CAE, sin omisión ni sustitución silenciosa. |
| Pantalla, API, importación y worker | Misma regla fiscal; los caminos válidos conservan su funcionamiento. |
| Cliente, plantilla o lote previo aún no emitido | Se conserva su información; se valida antes de una nueva solicitud y se permite corregir por el flujo vigente. |
| Comprobante autorizado, replay o solicitud incierta | Historia, payload y resultado preservados; la validación nueva no impide replay o reconciliación ni provoca otra emisión. |
| Corrección del receptor, concurrencia y fallos | Se preservan confirmación fiscal, idempotencia, aislamiento, numeración y recuperación vigentes. |

La cobertura usa datos sintéticos y dobles, sin llamadas reales de CAE en pruebas
automatizadas. La validación de integración en homologación se delimita al abrir
la implementación. El parche termina al demostrar este contrato; no incorpora
mejoras ajenas. Desplegar y comprobar producción requiere autorización separada
y el [flujo de producción](production-workflow.md).
