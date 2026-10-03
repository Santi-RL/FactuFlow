# Validación de planificación — confiabilidad e integración ARCA

Fecha: 03/10/2026.

Estado: evidencia de análisis y ensayos; no contrato de runtime ni certificación
productiva. El orden futuro vive en `ROADMAP.md`; los diseños son dueños de
invariantes y aceptación. Este dossier conserva los hechos que sustentan las
oportunidades incorporadas y su prioridad.

## Alcance y línea base

- FactuFlow: `4623647c809f8fbb40216f2c67ebf68b3d03d990`.
- Referencia: [LaPyme/facturas](https://github.com/LaPyme/facturas), snapshot
  `118f53404ef03f763298e5754ee319fb63d7cca9`.
- Se adaptan ideas al backend Python y al dominio existente; no se adopta su SDK
  Node ni se cambian `Decimal`, fechas explícitas o protecciones.
- Sólo documentación versionada. Sondas y copias en rutas ignoradas. No se
  modificó visión, código de aplicación, bases/certificados o configuración
  operativa; no se accedió al VPS ni se emitió o llamó a WSAA/WSFE/padrón reales.

## Entorno y barreras

Una copia de archivos versionados en `.tmp/roadmap-validation` excluyó `.env`,
certificados, bases y evidencia operativa. La imagen local usó dependencias
declaradas y bibliotecas nativas del Dockerfile del backend. Los ensayos usaron
`docker run --rm --network none`, SQLite efímero, worker desactivado y dobles ARCA.
Un `sitecustomize` adicional denegó conexiones. No se publicaron puertos ni
montaron volúmenes operativos.

El venv Windows encontró la advertencia de biblioteca HarfBuzz-Subset al importar
WeasyPrint. Se resolvió usando Docker, manteniendo advertencias como errores.
Los ensayos enfocados usaron `-o addopts=--tb=short`: una selección parcial no
evalúa cobertura global ni cambia el umbral/configuración versionados. No equivale
a CI completa, homologación ARCA o QA contable de las capacidades futuras.

## Resultados sobre código existente

| Hipótesis | Ensayo y observación | Consecuencia |
|---|---|---|
| Recuperación compara toda la solicitud | Camino legacy real con DB y grupo válido: coincidencia base, diferencia PES/DOL-cotización y cambio neto/IVA con igual total; los tres reconstruyen/autorizan desde payload local | Comparación legacy P1; recuperación moderna P2 separada |
| El camino moderno tiene la misma exposición | Pruebas de guarda huérfana y terminal moderno desde sesión antigua preservan inmovilización sin consultar/reemitir | No eliminar guardas RECE ni presentar legacy como bypass moderno |
| Lock de caché impide doble autenticación | Dos llamadas al cliente WSAA real con caché vacía y SOAP simulado producen dos autenticaciones | Coordinación completa y multiproceso P2 |
| Tickets están cifrados | Ticket sintético legible en JSON con el mecanismo actual | Cifrado y recuperación de claves PF-09, P2 |
| Revisión coincide con el backend | Helper y formateador real de `TotalesPanel.vue`: 0,5 unidades × 2,01 produce 1,005, mostrado como 1,01; backend devuelve 1,00. Controles 1,015 y 2,675 coinciden al mostrar dos decimales | Revisión P1 sin cambiar redondeo PF-03B; reutilización en PF-13 |
| Tasas sin soporte se rechazan | Schemas, validación de negocio con empresa/PV sintéticos y armado WSFE aceptan 2,5 %, 5 % y 19 %, produciendo neto 100, IVA 0, total 100. Sólo se aisló la ventana de fecha fija | Admisibilidad P1; soporte ampliado P2. No demuestra autorización real de ARCA |
| «Exento / 0 %» distingue categorías | Ítem 0 % produce neto 100, exento 0 y no gravado 0 | Definir semántica y ampliar dominio completo, no sólo etiquetas |

Las sondas verifican comportamiento observado, no su aceptación como correcto.
No demuestran casos afectados en una instalación ni justifican P0.

## Regresión enfocada y reproducción

- **125 pruebas existentes aprobadas**: WSAA (2), caché (12), WSFE (60), PF-03B
  (9), constancias (10), clientes (12), emisores (15) y cinco variantes de
  reconciliación/guardas/CAE conocido sin payload canónico.
- **8 sondas aprobadas**: tres consultas legacy, concurrencia/caché legible,
  representación de cero y tres alícuotas sin implementación.
- **41 pruebas frontend aprobadas** de `comprobante-items.spec.ts` y
  `ComprobanteNuevoView.spec.ts`.
- Comparación de helper/formateador reales con cálculo decimal; transpilación
  ES2022 para conservar iteración. Sin cambios de fuentes o reglas.

Selección adicional de backend:

```text
test_intento_stale_moderno_no_sobrescribe_terminal_desde_orm_obsoleto
test_intento_stale_legacy_se_bloquea_por_guarda_huerfana_operacion
test_intento_stale_no_libera_numero_con_error_arca_ambiguo
test_intento_stale_autorizado_preserva_cae_con_payload_no_canonico
```

La última tiene dos variantes. Corridas definitivas con código cero; los ajustes
iniciales de fixtures/entorno no se clasificaron como fallos de aplicación. No se
ensayó concurrencia PostgreSQL física ni migraciones; pertenecen a los cortes
que las implementen.

Los apéndices conservan las sondas temporales para reconstruir el experimento
sobre la línea base. El test Python usa `tests/conftest.py` versionado y se
ejecuta dentro del runtime aislado con `pytest … -q -o addopts=--tb=short`.
Las regresiones seleccionan los archivos/nodos anteriores. El frontend usa:

```powershell
npm --prefix frontend run test:unit -- src/utils/comprobante-items.spec.ts src/views/comprobantes/ComprobanteNuevoView.spec.ts
```

No trasladar las sondas a una instalación operativa ni convertir sus expectativas
del comportamiento actual en tests permanentes del comportamiento futuro.

## Padrón: fuente oficial y simulación

El [manual oficial de constancia, versión 4.1](https://www.arca.gob.ar/ws/WSCI/manual_ws_sr_ws_constancia_inscripcion.pdf)
documenta consulta por CUIT, credenciales/representación, datos registrales,
errores parciales y grupos de hasta 250 claves. El
[catálogo de ARCA](https://www.arca.gob.ar/ws/documentacion/catalogo.asp) identifica
el servicio vigente y la deprecación del alcance 5. El
[manual WSFE, revisión septiembre de 2026](https://www.arca.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG.pdf)
es referencia de campos fiscales. Consulta documental: 03/10/2026.

Un modelo temporal de deduplicación/caché, separado de FactuFlow, simuló:

| Filas | Sujetos únicos faltantes | Consultas agrupadas | Nuevas consultas con caché caliente |
|---|---|---|---|
| 20.000 | 200 | 1 | 0 |
| 20.000 | 800 | 4 | 0 |

La demora artificial de 20 ms por llamada no mide latencia, SLA o capacidad de
ARCA. El modelo comprobó régimen activo único y que ausencia, ambigüedad y
respuesta parcial dejan condición desconocida, sin default a consumidor final.
El mapeo definitivo exige códigos/estados oficiales; esta simulación no lo implementa.

Un cambio simulado monotributo → RI permaneció desconocido hasta renovar caché.
Se acepta consulta anticipada/agrupada, objetivo inicial configurable de renovación
de 24 horas y procedencia fechada; no vigencia instantánea ni bloqueo por
antigüedad sola. Medir el servicio autorizado y ajustar parámetros pertenece a
implementación, no a este ensayo.

Primer emisor: usar identidad ya habilitada o conservar manual/PDF y verificar
después; no depender circularmente de un certificado inexistente. Padrón no
acredita permisos, certificados, puntos de venta ni elegibilidad RECE.

## Ajustes de planificación

Mantener receptor P1 como siguiente unidad; adelantar importes/revisión y
comparación legacy P1 antes de recuperación/trazabilidad. Vincular snapshot y
recuperación moderna P2; priorizar WSAA P2 como base de padrón de clientes/emisores
P2, elevado por calidad fiscal. Categorías completas y notas son P2 con servicios
compartidos; historia externa opcional pasa a Más adelante. El roadmap mantiene
los demás compromisos y los diseños delimitan interacciones, aceptación y rollback.

Estos ensayos no autorizan implementación, publicación, despliegue ni emisiones.


## Apéndice A — sondas sobre backend

```python
"""Temporary probes: document observed behavior, not future implementation."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from app.arca import wsaa as wsaa_module
from app.arca.cache import TokenCache
from app.arca.config import ArcaAmbiente
from app.arca.wsaa import WSAAClient
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "currency", "tax"])
async def test_probe_reconciliation_path(db_session, test_empresa, change):
    modern=False
    pv = PuntoVenta(numero=1, nombre="Synthetic", activo=True,
                   es_webservice=True, empresa_id=test_empresa.id)
    lote = LoteComprobante(nombre_archivo="synthetic.xlsx", archivo_hash="a"*64,
        estado="procesando", total_filas=1, total_grupos=1, grupos_validos=1,
        empresa_id=test_empresa.id)
    db_session.add_all([pv,lote])
    await db_session.flush()
    request = EmitirComprobanteRequest(empresa_id=test_empresa.id,
        punto_venta_id=pv.id, tipo_comprobante=6, concepto=1,
        fecha_emision=date(2026,8,5), confirmacion_fecha_fiscal=True,
        tipo_documento=96, numero_documento="12345678", razon_social="Synthetic",
        condicion_iva="Consumidor Final", moneda="PES", cotizacion=Decimal("1"),
        items=[ItemComprobanteCreate(descripcion="Synthetic",cantidad=Decimal("1"),
              precio_unitario=Decimal("1000"),iva_porcentaje=Decimal("0"))])
    grupo=LoteComprobanteGrupo(lote_id=lote.id, empresa_id=test_empresa.id,
        comprobante_ref="SYN-1",orden=1,estado="validado",tipo_comprobante=6,
        punto_venta_numero=1,cliente_documento="12345678",cliente_razon_social="Synthetic",
        total_estimado=Decimal("1000"),payload_json=request.model_dump(mode="json"))
    db_session.add(grupo)
    await db_session.flush()
    intento=IntentoEmisionFiscal(empresa_id=test_empresa.id,punto_venta_id=pv.id,
        punto_venta_numero=1,tipo_comprobante=6,numero_planificado=1,
        fecha_emision=date(2026,8,5),total=Decimal("1000"),receptor_tipo_documento=96,
        receptor_numero_documento="12345678",receptor_razon_social="Synthetic",
        payload_hash="synthetic",huella_logica="synthetic",estado="en_proceso",
        lote_id=lote.id,grupo_id=grupo.id,ambiente="homologacion" if modern else None)
    db_session.add(intento)
    await db_session.commit()
    calls=0
    response=SimpleNamespace(resultado="A",cae="12345678901234",cae_vencimiento="20260819",
        cuit_emisor=test_empresa.cuit,tipo_cbte=6,punto_venta=1,numero=1,
        fecha_cbte="20260805",imp_total="1000",tipo_doc=96,nro_doc="12345678",
        moneda_id="DOL" if change=="currency" else "PES",
        moneda_cotiz=1500 if change=="currency" else 1,
        imp_neto="826.45" if change=="tax" else "1000",
        imp_iva="173.55" if change=="tax" else "0")
    class FakeQuery:
        async def fe_comp_consultar(self, **kwargs):
            nonlocal calls
            calls+=1
            return response
        async def fe_caesolicitar(self,*args,**kwargs):
            raise AssertionError("No CAE requests in this experiment")
    await FacturacionService(db_session)._reconciliar_intento_stale(
        intento=intento,wsfe_client=FakeQuery(),punto_venta_numero=1)
    await db_session.refresh(intento)
    cbte=await db_session.scalar(select(Comprobante))
    if modern:
        assert calls==0 and cbte is None and intento.estado=="en_proceso"
    else:
        assert calls==1 and intento.estado=="autorizado" and cbte is not None
        assert cbte.moneda=="PES" and cbte.iva_21==Decimal("0")
    print(f"OBSERVED reconciliation modern={modern} change={change} query_calls={calls} state={intento.estado}")


@pytest.mark.asyncio
async def test_probe_wsaa_concurrent_cache_miss(tmp_path,monkeypatch):
    cert=tmp_path/"synthetic.crt"
    cert.write_bytes(b"synthetic certificate")
    client=WSAAClient.__new__(WSAAClient)
    client.config=SimpleNamespace(ambiente=ArcaAmbiente.HOMOLOGACION)
    client.cache=TokenCache(storage_path=str(tmp_path/"synthetic-cache.json"))
    client.client=SimpleNamespace(service=SimpleNamespace(loginCms=lambda cms: None))
    monkeypatch.setattr(wsaa_module,"create_signed_tra",lambda **kw:"synthetic-cms")
    barrier=asyncio.Event()
    calls=0
    async def fake_soap(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:
            barrier.set()
        await asyncio.wait_for(barrier.wait(),timeout=2)
        expiry=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        return f"<loginTicketResponse><header><expirationTime>{expiry}</expirationTime></header><credentials><token>synthetic-token</token><sign>synthetic-sign</sign></credentials></loginTicketResponse>"
    monkeypatch.setattr(wsaa_module,"run_soap_call",fake_soap)
    await asyncio.gather(*[client.login(str(cert),"unused.key","20123456789") for _ in range(2)])
    assert calls==2
    assert "synthetic-token" in (tmp_path/"synthetic-cache.json").read_text()
    print(f"OBSERVED concurrent_WSAA_calls={calls}; persisted_ticket_plaintext=True")


def test_probe_zero_tax_representation():
    request=EmitirComprobanteRequest(empresa_id=1,punto_venta_id=1,tipo_comprobante=6,
        concepto=1,fecha_emision=date(2026,8,5),confirmacion_fecha_fiscal=True,
        tipo_documento=96,numero_documento="12345678",razon_social="Synthetic",
        condicion_iva="Consumidor Final",items=[ItemComprobanteCreate(descripcion="Synthetic",
            cantidad=Decimal("1"),precio_unitario=Decimal("100"),iva_porcentaje=Decimal("0"))])
    service=FacturacionService(None)
    totals=service._calcular_totales(request.items)
    arca=service._armar_request_arca(request,1,totals,1)
    assert arca.imp_op_ex==0 and arca.imp_tot_conc==0 and arca.imp_neto==100
    print("OBSERVED zero_rate: net=100 exempt=0 untaxed=0")


@pytest.mark.asyncio
@pytest.mark.parametrize("rate", ["2.5", "5", "19"])
async def test_probe_unsupported_rate_is_treated_as_zero(db_session,test_empresa,monkeypatch,rate):
    pv=PuntoVenta(numero=1,nombre="Synthetic",activo=True,es_webservice=True,empresa_id=test_empresa.id)
    db_session.add(pv)
    await db_session.commit()
    request=EmitirComprobanteRequest(empresa_id=test_empresa.id,punto_venta_id=pv.id,tipo_comprobante=6,
        concepto=1,fecha_emision=date(2026,8,5),confirmacion_fecha_fiscal=True,
        tipo_documento=96,numero_documento="12345678",razon_social="Synthetic",
        condicion_iva="Consumidor Final",items=[ItemComprobanteCreate(descripcion="Synthetic",
            cantidad=Decimal("1"),precio_unitario=Decimal("100"),iva_porcentaje=Decimal(rate))])
    service=FacturacionService(db_session)
    monkeypatch.setattr(service,"_validar_fecha_emision_arca",lambda *args:None)
    await service._validar_datos(request)
    totals=service._calcular_totales(request.items)
    arca=service._armar_request_arca(request,1,totals,1)
    assert totals["total"]==100 and arca.imp_iva==0 and arca.imp_neto==100
    print(f"OBSERVED unsupported_rate={rate} validation=accepted total=100 VAT=0")
```


## Apéndice B — cálculo y presentación frontend

```javascript
const fs = require('fs');
const ts = require('../../frontend/node_modules/typescript');
const source = fs.readFileSync('frontend/src/utils/comprobante-items.ts', 'utf8');
const helpers = {};
new Function('exports', ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(helpers);
const vue = fs.readFileSync('frontend/src/components/comprobantes/TotalesPanel.vue', 'utf8');
const start = vue.indexOf('const formatMonto = ');
const end = vue.indexOf('\n};',start)+3;
const fn = vue.slice(start,end) + '\nreturn formatMonto;';
const format = new Function(ts.transpileModule(fn,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)();
for(const price of [1.005,1.015,2.675]) {
  const result = helpers.calcularImportesItems([{descripcion:'Synthetic',cantidad:1,precio_unitario:price,descuento_porcentaje:0,iva_porcentaje:0}]);
  console.log(JSON.stringify({price,error:result.error,total:result.totales.total,display:format(result.totales.total)}));
}
const rate = helpers.calcularImportesItems([{descripcion:'Synthetic',cantidad:1,precio_unitario:100,descuento_porcentaje:0,iva_porcentaje:5}]);
console.log(JSON.stringify({rate5:rate}));
const fraction = helpers.calcularImportesItems([{descripcion:'Synthetic',cantidad:0.5,precio_unitario:2.01,descuento_porcentaje:0,iva_porcentaje:0}]);
console.log(JSON.stringify({quantity:0.5,price:2.01,total:fraction.totales.total,display:format(fraction.totales.total)}));
```


## Apéndice C — simulación de caché y consultas agrupadas

```python
"""Model of batch/cache policy, not an implementation in FactuFlow."""
import asyncio, math, time

async def prepare(rows, cache, fetch):
    unique=list(dict.fromkeys(rows))
    missing=[key for key in unique if key not in cache]
    for start in range(0,len(missing),250):
        result=await fetch(missing[start:start+250])
        # Absent/incomplete entries remain unknown, not Consumer Final.
        for key,value in result.items():
            if value is not None:
                cache[key]=value
    return {key:cache.get(key) for key in unique}

def classify(active, complete=True):
    if not complete:
        return None
    known=set(active)&{'IVA','MONOTRIBUTO','IVA_EXENTO'}
    return {'IVA':'RI','MONOTRIBUTO':'Monotributo','IVA_EXENTO':'Exento'}.get(next(iter(known))) if len(known)==1 else None

async def main():
    for count in [200,800]:
        rows=[f'synthetic-{i%count}' for i in range(20000)]
        calls=0
        async def fetch(keys):
            nonlocal calls
            calls+=1
            await asyncio.sleep(0.02)  # Artificial delay, not ARCA latency.
            return {key:'Monotributo' for key in keys}
        cache={}
        start=time.perf_counter()
        data=await prepare(rows,cache,fetch)
        elapsed=time.perf_counter()-start
        assert calls==math.ceil(count/250) and len(data)==count
        cold_calls=calls
        start=time.perf_counter()
        await prepare(rows,cache,fetch)
        warm=time.perf_counter()-start
        assert calls==cold_calls
        print(f'rows=20000 unique={count} cold_calls={calls} warm_new_calls=0 cold_simulated_ms={elapsed*1000:.1f} warm_ms={warm*1000:.1f}')
    assert classify(['MONOTRIBUTO'])=='Monotributo'
    assert classify(['IVA'])=='RI'
    assert classify(['IVA_EXENTO'])=='Exento'
    assert classify([]) is None
    assert classify(['IVA','MONOTRIBUTO']) is None
    assert classify(['IVA'],False) is None
    async def partial(keys):
        return {keys[0]:'RI'}
    result=await prepare(['one','two'],{},partial)
    assert result['one']=='RI' and result['two'] is None
    print('policy assertions: active regime recognized; missing, conflicting, partial and absent remain unknown')
    # An observation cannot guarantee the taxpayer did not change after reading.
    cache={'one':'Monotributo'}
    async def changed(keys):
        return {'one':'RI'}
    assert (await prepare(['one'],cache,changed))['one']=='Monotributo'
    cache.pop('one')  # Refresh scheduled before preparation, outside CAE path.
    assert (await prepare(['one'],cache,changed))['one']=='RI'
    print('staleness: cache retained old status until refresh; no instantaneous-freshness claim')

asyncio.run(main())
```
