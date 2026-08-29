# QA visual — puntos de venta 0.3.2

- Fuente aprobada: Figma `TEplbyVwwJx7PKKNG50iSu`, frame `2:3`.
- Implementación: `frontend/src/views/PuntosVentaView.vue`.
- Referencia: `.tmp/figma-qa/puntos-venta-ux.png` (1440 × 910).
- Captura comparada: `.tmp/figma-qa/puntos-venta-0.3.2-crop.png` (1440 × 910).
- Comparación conjunta: `.tmp/figma-qa/puntos-venta-comparison.png`.
- Viewports comprobados: 1700 × 1000, 1440 × 900, 1024 × 768 y 390 × 844.

## Resultado

- Tipografía: jerarquía, peso y tamaños consistentes con la pantalla aprobada.
- Espaciado y disposición: encabezado, acciones, resumen, filtro, tabla y estados mantienen la estructura y el ritmo visual de Figma.
- Adaptación: el contenido conserva su jerarquía; en pantallas angostas la navegación se repliega, las acciones se apilan y la tabla permite desplazamiento horizontal.
- Colores y componentes: se reutilizan los tokens, bordes, radios, botones, avisos y etiquetas del sistema existente.
- Recursos e iconos: no hay imágenes decorativas; los iconos provienen de la biblioteca Heroicons ya usada por FactuFlow.
- Interacción: el filtro funciona, la comprobación fallida deja visibles los puntos frescos y excluye los pendientes, y el selector de emisión sólo ofrece puntos comprobados.
- Accesibilidad: los controles conservan etiquetas visibles, foco nativo, estados deshabilitados y textos accionables.
- Contenido: se eliminaron los términos técnicos y los estados normales sólo muestran la información necesaria. La diferencia funcional intencional respecto del frame es que el estado pendiente se presenta como `Comprobación necesaria` y no es seleccionable.

No se detectaron desvíos P0–P2.

passed
