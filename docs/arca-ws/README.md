# Documentación ARCA WS dentro del proyecto

Última actualizacion: 2026-03-09

Esta carpeta guarda la documentación local necesaria para trabajar con ARCA sin depender siempre de internet. La fuente oficial sigue siendo `https://www.arca.gob.ar/ws/`.

## Como usar esta carpeta

Empezar por aca:
- `docs/arca-ws/NOTAS.md` para hallazgos practicos
- `docs/agents/arca.md` para el estado de integración del proyecto

Ir después a los documentos originales segun el tema.

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

- `docs/arca-ws/wsfe/manual-desarrollador-ARCA-COMPG-v4-1.pdf`
- `docs/arca-ws/wsfe/Web-Service-MTXCA-v25.pdf`
- `docs/arca-ws/wsfe/Manual_Desarrollador_WSCT_v1.6.4.pdf`
- `docs/arca-ws/wsfe/WSFEX-Manualparaeldesarrollador_V3.1.1_ARCA.pdf`
- `docs/arca-ws/wsfe/WSSEG-ManualParaElDesarrollador_ARCA.pdf`

## Hallazgos de esta sesión que conviene recordar

- Para homologación se usó WSASS para emitir el certificado y autorizar `wsfe`.
- La validación confiable de comprobantes homologación es `FECompConsultar`.
- En homologación, `FEParamGetPtosVenta` puede responder `602 - Sin Resultados`.
- `CondicionIVAReceptorId` fue obligatoria para emitir en homologación.

Estos puntos estan desarrollados en:
- `docs/arca-ws/NOTAS.md`
- `docs/agents/arca.md`

## Limpieza de esta carpeta

- La carpeta generada `docs/arca-ws/_extracted/` se elimino del repo el 2026-03-09 porque era derivada y redundante.
- Si hace falta volver a generarla localmente, usar `scripts/arca_ws_extract.py`.

## Regla de mantenimiento

Cuando se descubra un comportamiento nuevo de ARCA:
- resumirlo primero en `docs/arca-ws/NOTAS.md`
- si impacta al producto, reflejarlo también en `docs/agents/arca.md`
