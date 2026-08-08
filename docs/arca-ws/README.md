# Documentación ARCA WS dentro del proyecto

Última actualización: 08/08/2026

Esta carpeta guarda documentación local de apoyo para trabajar con ARCA. La
autoridad vigente continúa en los sitios oficiales; una copia local histórica
no reemplaza el manual publicado actualmente.

## Cómo usar esta carpeta

Empezar por acá:
- `docs/arca-ws/NOTAS.md` para hallazgos prácticos
- `docs/agents/arca.md` para el estado de integración del proyecto

Ir después a los documentos originales según el tema.

## Autoridad vigente de WSFEv1

Fuente consultada el 08/08/2026:

- [Índice oficial de factura electrónica de ARCA](https://arca.gob.ar/ws/documentacion/ws-factura-electronica.asp),
  que enlaza el `Manual para el desarrollador V. 4.6`.
- [Manual oficial WSFEv1 v4.6](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf),
  revisión 01/08/2026.
- Regla `10005`: `FECAESolicitar` → `Validaciones y errores` → `Controles
  aplicados al objeto <FeCabReq>` → `Validaciones Excluyentes`, campo
  `<PtoVta>`, página 40 del PDF. La validación exige que el punto esté dado de
  alta y sea RECE.

## Documentos prioritarios

### WSAA

- `docs/arca-ws/wsaa/Especificacion_Tecnica_WSAA_1.2.2.pdf`
- `docs/arca-ws/wsaa/WSAAmanualDev.pdf`
- `docs/arca-ws/wsaa/WSAA.ObtenerCertificado.pdf`
- `docs/arca-ws/wsaa/ADMINREL.DelegarWS.pdf`

### WSASS y certificados

- `docs/arca-ws/wsass/WSASS_como_adherirse.pdf`
- `docs/arca-ws/wsass/WSASS_manual.pdf`
- `docs/arca-ws/wsass/WSASS_html_index.html`
- `docs/arca-ws/wsass/introduccion-servicios.md`
- `docs/arca-ws/certificados/`

### Facturación y servicios relacionados

- `docs/arca-ws/wsfe/manual-desarrollador-ARCA-COMPG-v4-1.pdf`: copia local
  histórica v4.1; no sustituye la autoridad oficial vigente v4.6.
- `docs/arca-ws/wsfe/Web-Service-MTXCA-v25.pdf`
- `docs/arca-ws/wsfe/Manual_Desarrollador_WSCT_v1.6.4.pdf`
- `docs/arca-ws/wsfe/WSFEX-Manualparaeldesarrollador_V3.1.1_ARCA.pdf`
- `docs/arca-ws/wsfe/WSSEG-ManualParaElDesarrollador_ARCA.pdf`

## Hallazgos de esta sesión que conviene recordar

- Para homologación se usó WSASS para emitir el certificado y autorizar `wsfe`.
- La validación confiable de comprobantes homologación es `FECompConsultar`.
- En homologación, `FEParamGetPtosVenta` puede responder `602 - Sin Resultados`.
- `CondicionIVAReceptorId` fue obligatoria para emitir en homologación.

Estos puntos están desarrollados en:
- `docs/arca-ws/NOTAS.md`
- `docs/agents/arca.md`

## Limpieza de esta carpeta

- La carpeta generada `docs/arca-ws/_extracted/` se eliminó del repo el
  09/03/2026 porque era derivada y redundante.
- Si hace falta volver a generarla localmente, usar `scripts/arca_ws_extract.py`.

## Regla de mantenimiento

Cuando se descubra un comportamiento nuevo de ARCA:
- resumirlo primero en `docs/arca-ws/NOTAS.md`
- si impacta al producto, reflejarlo también en `docs/agents/arca.md`
