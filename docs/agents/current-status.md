# Estado aceptado del repositorio

Última revisión: 04/10/2026

Estado: VIGENTE.

Este documento es un handoff breve sobre lo aceptado en el repositorio. No
conserva historia de implementación, evidencia de CI ni el estado de una
instalación concreta.

El estado desplegado autoritativo vive en el plano de control `VPS Hostinger` /
`vps-admin`. No se infiere desde `main`, una release, un tag ni este documento.

## Línea base aceptada

- La release publicada más reciente es `v0.3.6`.
- El producto usa backend FastAPI, frontend Vue 3 y Alembic como camino canónico
  de esquema para PostgreSQL.
- FactuFlow admite emisión individual y masiva, clientes, comprobantes, PDFs,
  reportes, certificados, puntos de venta, perfiles y formatos de importación.
- El modelo actual mantiene un emisor activo explícito por vez.
- Los operadores tienen cero, uno o varios accesos explícitos por emisor. Una
  capacidad separada permite crear y editar emisores asignados sin conceder
  administración global ni borrado.
- Las operaciones fiscales preservan fecha explícita, confirmación irreversible,
  idempotencia, intentos durables y reconciliación cuando ARCA pudo autorizar.
- PF-01, PF-02, PF-03A/PF-03B, PF-06/PF-07/PF-08 y
  PF-19A/PF-19B/PF-19C/PF-19D están cerrados.
- `v0.3.5` incorpora accesos explícitos de cero, uno o varios emisores por
  operador y separa la capacidad de crear y editar fichas de la administración
  global del sistema.
- `v0.3.4` usa WSFE como autoridad autenticada de puntos CAE por emisor y
  ambiente, separa su estado técnico de la preferencia compartida de uso y deja
  la constancia como complemento descriptivo opcional.
- La selección comprueba puntos WSFE desactualizados antes de habilitar opciones
  y conserva el preflight final del servidor.

La conducta aceptada de puntos de venta usa `FEParamGetPtosVenta` como autoridad
técnica por emisor y ambiente. Los puntos CAE compatibles quedan separados de
la preferencia compartida `Usar en FactuFlow`; la constancia es opcional y sólo
completa domicilio, nombre de fantasía y puntos informativos de otros sistemas.
La revisión fiscal, el preflight de 90 días, la idempotencia y la reconciliación
permanecen vigentes.

## Contrato de prevención de duplicados

La emisión masiva distingue repeticiones internas de receptores identificables
y coincidencias de contenido entre lotes del mismo emisor y ambiente. Las
ventas anónimas que sólo repiten fecha e importe dentro del lote no generan
una advertencia interna. La comparación histórica completa sí incluye lotes
anónimos; nombre de archivo, cantidad e importe total no bastan para probarla.

El aviso identifica antecedentes y usuario de emisión, prioriza «Volver a
revisar» y exige una aceptación específica para operaciones nuevas. La
revalidación y las reservas concurrentes preservan idempotencia, confirmación
fiscal y estados inciertos. Un reintento parcial conserva los comprobantes
autorizados y sólo vuelve a enviar los fallidos.

Los remanentes antiguos cuya aceptación no puede reconstruirse y tienen
coincidencias actuales quedan bloqueados para continuar o reintentar. Se
conservan historia, replay terminal y reconciliación. El alcance preciso de
compatibilidad y el contrato técnico viven en el
[diseño de duplicados](pf-13-duplicados-lotes-design.md); los cambios de la
unidad se consultan en `CHANGELOG.md > 0.3.6`. El corte está publicado en
`v0.3.6` y su [dossier](../project/releases/pf13-duplicados-candidate.md) reúne
evidencia de publicación, migraciones y recuperación. El despliegue requiere
autorización separada y no se acredita desde este estado.

## Contrato de reintentos seguros

El reintento confirmado usa cola durable y el camino masivo por bloques. Sólo
procesa su selección y conserva los autorizados anteriores. El progreso de la
operación actual se recupera al volver al lote. Los fallos demostrados previos
a CAE cierran pendientes y reservas propias; recuperar reservas antiguas exige
propietario terminal y ausencia de intentos/guardas activos o inciertos. Los
resultados posteriores al envío conservan reconciliación. La API síncrona
anterior permanece compatible. El [contrato](pf-13-17-reintentos-seguros-parche.md)
y el [dossier](../project/releases/pf13-17-reintentos-seguros.md) delimitan el corte.

## Trabajo aceptado pendiente

El frontend usa Tailwind 4.3.3 y su plugin PostCSS; la cadena vulnerable de
construcción anterior fue retirada, conservando marca, escalas y foco accesible.
El [contrato de navegadores](../../frontend/README.md#navegadores-compatibles)
acepta Firefox 128+. CI conserva sus gates y usa Ubuntu 24.04 explícito.
Las alertas de herramientas Python de desarrollo son un corte distinto pendiente;
no están cubiertas por la auditoría de `requirements.txt` ni cierran PF-16.

Los instantes operativos de la API comunican UTC explícito y la web muestra
hora argentina en lotes, usuarios, emisor y Sistema, independientemente de la
zona del navegador. Fechas fiscales y antecedentes de zona desconocida conservan
su tratamiento. El [contrato temporal](pf-12-15-17-tiempo-operativo.md) delimita
compatibilidad y consumidores; no hay migración ni desplazamiento de la base.

La auditoría integral corrigió documentación, código sin consumidores, fechas de
calendario, contexto de detalles/formularios, errores PDF y barreras de
construcción. Conserva los contratos fiscales y la visión. Los hallazgos de
capacidad de persistencia, lecturas y dependencias permanecen abiertos y forman
una puerta de estabilización antes de capacidades nuevas. Evidencia y límites en el
[dossier de auditoría](../project/analysis/auditoria-integral-2026-10.md);
responsabilidades compartidas y horizonte MCP en
[dirección de arquitectura](architecture-direction.md). No acredita despliegue.

La asociación administrativa A-02 está corregida en el guardado compartido:
varias fichas coincidentes conservan el snapshot receptor sin elegir una al
azar ni impedir guardar el CAE. Selección explícita, transacción, errores reales
y reconciliación conservan su conducta. El
[contrato](pf-03-04-14-asociacion-cliente.md) delimita los cuatro consumidores;
no cierra capacidad A-01 ni introduce unicidad de clientes.

La entrega de reintentos incluye correcciones de dependencias y una CI sin
advertencias: PyJWT/WeasyPrint, auditoría npm completa, compatibilidad bcrypt,
APIs Pydantic/FastAPI vigentes y puertas estrictas de lint y pytest. El
[dossier](../project/releases/pf13-17-reintentos-seguros.md) conserva alcance y
validación. El despliegue sigue requiriendo SHA exacto y evidencia del plano
de control; este resumen no acredita una instalación.

El orden y alcance macro del trabajo pendiente se consultan exclusivamente en
[`ROADMAP.md`](../../ROADMAP.md). El detalle completo está en
[`development-portfolio.md`](development-portfolio.md) y los diseños enlazados.
No duplicar aquí la secuencia: una línea puede tener varios cortes con
prioridades y horizontes diferentes. Los diseños futuros no describen
capacidades implementadas. La revisión visual local acordada para la UI de
lotes permanece en su diseño y precede a la publicación de esa implementación.

Está aceptada la planificación integrada de importes/previsualización,
reconciliación integral, WSAA coordinado/cifrado, padrón para clientes y emisores,
y notas guiadas. Los ensayos justifican cortes fiscales acotados y el uso de
padrón anticipado, con fuente fechada y sin consulta obligatoria en el tramo de
CAE. La [validación de planificación](../project/analysis/confiabilidad-arca-roadmap.md)
conserva evidencia y límites; los contratos futuros se consultan desde el
[índice de diseños](README.md#diseños-activos). Esta planificación no modifica
runtime, no acredita una instalación ni cambia los cierres históricos.

## Condición IVA del receptor

Toda nueva solicitud individual, masiva o de reintento envía un ID presente y
compatible con el comprobante. Las condiciones soportadas son RI y Monotributo
para A, Exento y CF para B, y las cuatro para C. Valores vacíos, desconocidos,
RNI o incompatibles requieren corrección explícita; no se infieren por documento.
Los formatos con una condición fija válida conservan su funcionamiento. Replay,
historia y reconciliación mantienen el contrato vigente. El
[contrato RG 5616](rg-5616-condicion-iva-receptor-parche.md) y su
[dossier](../project/releases/rg5616-condicion-iva.md) delimitan el parche.

El cierre del parche no acredita fidelidad completa de identificación en la
importación configurable: ésta aún puede descartar el documento de CF bajo el
umbral y la validación del lote rechaza CUIT con CF. La combinación es admisible
en la normativa; la diferencia entre caminos y su corrección pendiente están
delimitadas en el [diseño de fidelidad del receptor](pf-13-receptores-importacion-design.md).
Ese diseño futuro no describe una corrección ya implementada. Las condiciones
siguen siendo datos explícitos, independientes del documento.

## Punto de reanudación

Los parches de reintentos seguros y condición IVA están cerrados en código.
La evidencia se consulta en sus dossiers; el estado productivo se acredita sólo
en el plano de control. Una publicación o despliegue no inicia la siguiente unidad.

Para continuar desarrollo:

1. verificar `git status --short --branch` y sincronía con `origin/main`;
2. leer `VISION.md` y la primera unidad de `ROADMAP.md`;
3. abrir únicamente el diseño y los runbooks indicados para esa unidad;
4. si el cambio es fiscal, completar `fiscal-change-checklist.md` antes de
   implementar;
5. no consultar ni modificar producción sin una autorización explícita y el
   enrutamiento establecido hacia `vps-admin`.

No se debe reconstruir el contexto leyendo auditorías o diseños cerrados. Para
historia usar `CHANGELOG.md`, dossiers o
[`docs/project/history/`](../project/history/README.md).

## Fuentes relacionadas

- Visión y decisiones de producto: [`VISION.md`](../../VISION.md)
- Prioridades: [`ROADMAP.md`](../../ROADMAP.md)
- Portafolio pendiente: [`development-portfolio.md`](development-portfolio.md)
- Arquitectura estable: [`overview.md`](overview.md)
- Índice para agentes: [`README.md`](README.md)
- Historial de versiones: [`CHANGELOG.md`](../../CHANGELOG.md)
