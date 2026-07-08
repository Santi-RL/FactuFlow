<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import { useNotification } from "@/composables/useNotification";
import {
  esProvinciaArgentina,
  normalizarProvinciaArgentina,
  provinciasOptions,
} from "@/constants/provincias";
import formatosImportacionService from "@/services/formatos-importacion.service";
import perfilesCargaMasivaService from "@/services/perfiles-carga-masiva.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import type {
  FormatoImportacion,
  FormatoImportacionCampoCatalogo,
  FormatoImportacionCompatibilidad,
  FormatoImportacionPayload,
} from "@/types/formato-importacion";
import type { Empresa, EmpresaCreate, EmpresaUpdate } from "@/types/empresa";
import type {
  PerfilCargaMasiva,
  PerfilCargaMasivaConfiguracion,
  PerfilCargaMasivaPayload,
} from "@/types/perfil-carga-masiva";
import type { PuntoVenta } from "@/types/punto_venta";
import { configuracionPerfilVacia } from "@/utils/perfiles-carga-masiva";
import {
  ArrowDownIcon,
  ArrowDownTrayIcon,
  ArrowUpIcon,
  BuildingOffice2Icon,
  CalendarDaysIcon,
  CheckCircleIcon,
  DocumentDuplicateIcon,
  DocumentArrowUpIcon,
  ExclamationTriangleIcon,
  IdentificationIcon,
  PencilSquareIcon,
  PlusIcon,
  StarIcon,
  TrashIcon,
} from "@heroicons/vue/24/outline";
import { empresaService } from "@/services/empresa.service";

const authStore = useAuthStore();
const empresaStore = useEmpresaStore();
const { showError, showSuccess } = useNotification();

type PlantillaOrigen = "header" | "columna" | "constante" | "empresa";

interface PlantillaColumnaForm {
  id: string;
  etiqueta: string;
  campo_destino: string;
  origen: PlantillaOrigen;
  valor: string;
  transformacion: string;
  requerido: boolean;
  ejemplo: string;
  letra_columna: string;
  indice_columna: string;
}

const loading = ref(true);
const saving = ref(false);
const creating = ref(false);
const loadingPerfiles = ref(false);
const savingPerfil = ref(false);
const savingPlantilla = ref(false);
const showCreateModal = ref(false);
const showPerfilModal = ref(false);
const showPlantillaModal = ref(false);
const perfilEditando = ref<PerfilCargaMasiva | null>(null);
const perfilAEliminar = ref<PerfilCargaMasiva | null>(null);
const plantillaEditando = ref<FormatoImportacion | null>(null);
const plantillaAEliminar = ref<FormatoImportacion | null>(null);
const extractingConstancia = ref(false);
const constanciaInput = ref<HTMLInputElement | null>(null);
const plantillaExcelInput = ref<HTMLInputElement | null>(null);
const extractionWarnings = ref<string[]>([]);
const activeTab = ref<"datos" | "carga-masiva">("datos");
const cargaMasivaTab = ref<"perfiles" | "plantillas">("perfiles");
const perfilesCargaMasiva = ref<PerfilCargaMasiva[]>([]);
const formatosImportacion = ref<FormatoImportacion[]>([]);
const catalogoCampos = ref<FormatoImportacionCampoCatalogo[]>([]);
const puntosVenta = ref<PuntoVenta[]>([]);
const compatibilidadPlantilla = ref<FormatoImportacionCompatibilidad | null>(
  null,
);
const evaluandoCompatibilidad = ref(false);
let compatibilidadPlantillaTimer: ReturnType<typeof setTimeout> | undefined;

const empresaActiva = computed(() => empresaStore.empresaActiva);
const condicionIvaOptions = [
  { value: "RI", label: "Responsable Inscripto" },
  { value: "Monotributo", label: "Monotributo" },
  { value: "Exento", label: "Exento" },
];
const conceptoPerfilOptions = [
  { value: "", label: "Completar en carga masiva" },
  { value: "productos", label: "Productos" },
  { value: "servicios", label: "Servicios" },
  { value: "archivo", label: "Definido por el archivo" },
];
const descripcionPerfilOptions = [
  { value: "", label: "Completar en carga masiva" },
  { value: "archivo", label: "Utilizar descripción del archivo" },
  { value: "fija", label: "Utilizar descripción fija" },
];
const fechaEmisionPerfilOptions = [
  { value: "manual", label: "Completar en carga masiva" },
  { value: "archivo", label: "Utilizar fecha del archivo" },
  { value: "personalizada", label: "Fecha personalizada" },
];
const periodoPerfilOptions = [
  { value: "manual", label: "Completar en carga masiva" },
  { value: "archivo", label: "Utilizar fechas del archivo" },
  { value: "mes_anterior_completo", label: "Mes anterior completo" },
  { value: "mes_actual_completo", label: "Mes actual completo" },
  { value: "personalizado", label: "Periodo personalizado" },
];
const vencimientoPerfilOptions = [
  { value: "manual", label: "Completar en carga masiva" },
  { value: "archivo", label: "Utilizar vencimiento del archivo" },
  { value: "mismo_dia_emision", label: "Mismo día de emisión" },
  { value: "emision_mas_dias", label: "Fecha de emisión + días" },
  { value: "personalizada", label: "Fecha personalizada" },
];
const alcancePlantillaOptions = computed(() => [
  { value: "emisor", label: "Solo este emisor" },
  ...(authStore.user?.es_admin
    ? [{ value: "global", label: "Global para todos los emisores" }]
    : []),
]);
const origenPlantillaOptions = [
  { value: "header", label: "Columna visible" },
  { value: "columna", label: "Letra/posición del Excel" },
  { value: "constante", label: "Valor fijo" },
  { value: "empresa", label: "Dato del emisor" },
];
const transformacionPlantillaOptions = [
  { value: "", label: "Sin transformación" },
  { value: "texto", label: "Texto" },
  { value: "decimal", label: "Número decimal" },
  { value: "entero", label: "Número entero" },
  { value: "fecha", label: "Fecha" },
  { value: "documento", label: "Documento/CUIT" },
];

const crearFormularioVacio = () => ({
  razon_social: "",
  cuit: "",
  condicion_iva: "RI",
  ingresos_brutos: "",
  domicilio: "",
  localidad: "",
  provincia: "",
  codigo_postal: "",
  email: "",
  telefono: "",
  inicio_actividades: "",
});

const form = reactive(crearFormularioVacio());
const createForm = reactive(crearFormularioVacio());
const perfilForm = reactive({
  nombre: "",
  descripcion: "",
  es_predeterminado: false,
  configuracion: configuracionPerfilVacia(),
});
const plantillaForm = reactive({
  nombre: "",
  descripcion: "",
  alcance: "emisor" as "global" | "emisor",
  columnas: [] as PlantillaColumnaForm[],
});
const camposCatalogoOptions = computed(() => [
  { value: "", label: "Seleccionar campo" },
  ...catalogoCampos.value.map((campo) => ({
    value: campo.codigo,
    label: `${campo.etiqueta} · ${campo.grupo}`,
  })),
]);
const plantillasDisponibles = computed(() =>
  formatosImportacion.value.filter((formato) => formato.activo),
);
const formatosOptions = computed(() => [
  { value: "", label: "Sin plantilla preseleccionada" },
  ...formatosImportacion.value
    .filter((formato) => !!formato.version_vigente)
    .map((formato) => ({
      value: formato.version_vigente?.id || "",
      label: `${formato.nombre} (${formato.alcance})`,
    })),
]);
const puntosVentaFactuflow = computed(() =>
  puntosVenta.value.filter((punto) => punto.usable_factuflow),
);
const puntoVentaPerfilOptions = computed(() => [
  { value: "archivo", label: "Utilizar punto de venta definido en el archivo" },
  ...puntosVentaFactuflow.value.map((punto) => ({
    value: `fijo:${punto.numero}`,
    label: `${String(punto.numero).padStart(4, "0")}${
      punto.nombre ? ` - ${punto.nombre}` : ""
    }`,
  })),
]);
const perfilPuntoVentaSeleccionado = computed({
  get: () => {
    const regla = perfilForm.configuracion.punto_venta || { modo: "archivo" };
    if (regla.modo === "fijo" && regla.numero) {
      return `fijo:${regla.numero}`;
    }
    return "archivo";
  },
  set: (value: string | number) => {
    const selected = String(value || "archivo");
    if (selected.startsWith("fijo:")) {
      perfilForm.configuracion.punto_venta = {
        modo: "fijo",
        numero: Number(selected.replace("fijo:", "")) || null,
      };
      return;
    }
    perfilForm.configuracion.punto_venta = { modo: "archivo", numero: null };
  },
});
const perfilFormatoImportacionVersionId = computed({
  get: () => perfilForm.configuracion.formato_importacion_version_id || "",
  set: (value: string | number) => {
    perfilForm.configuracion.formato_importacion_version_id =
      Number(value || 0) || null;
  },
});

const sincronizarFormulario = (empresa: Empresa | null) => {
  if (!empresa) return;

  form.razon_social = empresa.razon_social;
  form.cuit = empresa.cuit;
  form.condicion_iva = empresa.condicion_iva;
  form.ingresos_brutos = empresa.ingresos_brutos || "";
  form.domicilio = empresa.domicilio;
  form.localidad = empresa.localidad;
  form.provincia = normalizarProvinciaArgentina(empresa.provincia) || "";
  form.codigo_postal = empresa.codigo_postal;
  form.email = empresa.email || "";
  form.telefono = empresa.telefono || "";
  form.inicio_actividades = empresa.inicio_actividades;
};

const resetCreateForm = () => {
  Object.assign(createForm, crearFormularioVacio());
};

const resetPerfilForm = () => {
  perfilForm.nombre = "";
  perfilForm.descripcion = "";
  perfilForm.es_predeterminado = false;
  perfilForm.configuracion = configuracionPerfilVacia();
};

const sincronizarPerfilForm = (perfil: PerfilCargaMasiva) => {
  perfilForm.nombre = perfil.nombre;
  perfilForm.descripcion = perfil.descripcion || "";
  perfilForm.es_predeterminado = perfil.es_predeterminado;
  perfilForm.configuracion = {
    ...configuracionPerfilVacia(),
    ...perfil.configuracion_json,
    punto_venta: {
      ...configuracionPerfilVacia().punto_venta,
      ...(perfil.configuracion_json.punto_venta || {}),
    },
    fecha_emision: {
      ...configuracionPerfilVacia().fecha_emision,
      ...(perfil.configuracion_json.fecha_emision || {}),
    },
    periodo_servicio: {
      ...configuracionPerfilVacia().periodo_servicio,
      ...(perfil.configuracion_json.periodo_servicio || {}),
    },
    fecha_vto_pago: {
      ...configuracionPerfilVacia().fecha_vto_pago,
      ...(perfil.configuracion_json.fecha_vto_pago || {}),
    },
  };
};

const crearColumnaPlantilla = (
  data: Partial<PlantillaColumnaForm> = {},
): PlantillaColumnaForm => ({
  id: crypto.randomUUID(),
  etiqueta: data.etiqueta || "",
  campo_destino: data.campo_destino || "",
  origen: data.origen || "header",
  valor: data.valor || "",
  transformacion: data.transformacion || "",
  requerido: data.requerido ?? false,
  ejemplo: data.ejemplo || "",
  letra_columna: data.letra_columna || "",
  indice_columna: data.indice_columna || "",
});

const resetPlantillaForm = () => {
  plantillaForm.nombre = "";
  plantillaForm.descripcion = "";
  plantillaForm.alcance = "emisor";
  plantillaForm.columnas = [
    crearColumnaPlantilla({
      etiqueta: "Tipo comprobante",
      campo_destino: "tipo_comprobante",
      origen: "constante",
      valor: "11",
      requerido: true,
    }),
    crearColumnaPlantilla({
      etiqueta: "Fecha emisión",
      campo_destino: "fecha_emision",
      requerido: true,
      transformacion: "fecha",
      ejemplo: "2026-05-31",
    }),
    crearColumnaPlantilla({
      etiqueta: "Documento receptor",
      campo_destino: "cliente_numero_documento",
      transformacion: "documento",
      ejemplo: "30123456789",
    }),
    crearColumnaPlantilla({
      etiqueta: "Descripción",
      campo_destino: "item_descripcion",
      requerido: true,
      transformacion: "texto",
      ejemplo: "Servicio mensual",
    }),
    crearColumnaPlantilla({
      etiqueta: "Precio unitario",
      campo_destino: "item_precio_unitario",
      requerido: true,
      transformacion: "decimal",
      ejemplo: "10000.00",
    }),
    crearColumnaPlantilla({
      etiqueta: "IVA",
      campo_destino: "item_iva_porcentaje",
      origen: "constante",
      valor: "0",
      requerido: true,
    }),
  ];
  compatibilidadPlantilla.value = null;
};

const esPlantillaProtegida = (formato: FormatoImportacion) =>
  Boolean(
    formato.version_vigente?.configuracion_json?.plantilla_sistema_protegida,
  );

const puedeAdministrarPlantilla = (formato: FormatoImportacion) =>
  !esPlantillaProtegida(formato) &&
  (formato.alcance !== "global" || Boolean(authStore.user?.es_admin));

const etiquetaAlcancePlantilla = (formato: FormatoImportacion) =>
  formato.alcance === "global" ? "Global" : "Emisor";

const columnasDesdeConfiguracion = (
  configuracion: Record<string, unknown>,
): PlantillaColumnaForm[] => {
  const campos = (configuracion.campos || {}) as Record<
    string,
    Record<string, unknown>
  >;
  const crearDesdeDetalle = (
    campo: string,
    detalle: Record<string, unknown>,
  ): PlantillaColumnaForm =>
    crearColumnaPlantilla({
      etiqueta:
        Array.isArray(detalle.encabezados) && detalle.encabezados.length > 0
          ? String(detalle.encabezados[0])
          : campo.replace(/_/g, " "),
      campo_destino: campo,
      origen: (String(detalle.origen || "header") as PlantillaOrigen) || "header",
      valor: String(detalle.valor ?? ""),
      transformacion: String(detalle.transformacion || ""),
      requerido: Boolean(detalle.requerido),
      letra_columna: String(detalle.letra_columna || ""),
      indice_columna:
        detalle.indice_columna === undefined
          ? ""
          : String(detalle.indice_columna),
    });
  const plantilla = configuracion.plantilla as
    | { columnas?: Array<Record<string, unknown>> }
    | undefined;
  if (Array.isArray(plantilla?.columnas)) {
    const columnas = plantilla.columnas.map((columna) =>
      crearColumnaPlantilla({
        etiqueta: String(columna.etiqueta || ""),
        campo_destino: String(columna.campo_destino || ""),
        origen: (String(columna.origen || "header") as PlantillaOrigen) || "header",
        valor: String(columna.valor ?? ""),
        transformacion: String(columna.transformacion || ""),
        requerido: Boolean(columna.requerido),
        ejemplo: String(columna.ejemplo || ""),
        letra_columna: String(columna.letra_columna || ""),
        indice_columna:
          columna.indice_columna === undefined
            ? ""
            : String(columna.indice_columna),
      }),
    );
    const camposVisuales = new Set(columnas.map((columna) => columna.campo_destino));
    for (const [campo, detalle] of Object.entries(campos)) {
      if (!camposVisuales.has(campo)) {
        columnas.push(crearDesdeDetalle(campo, detalle));
      }
    }
    return columnas;
  }

  return Object.entries(campos).map(([campo, detalle]) =>
    crearDesdeDetalle(campo, detalle),
  );
};

const parseValorConstantePlantilla = (value: string) => {
  const trimmed = value.trim();
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  return trimmed;
};

const construirConfiguracionPlantilla = (): Record<string, unknown> => {
  const configuracionActual =
    plantillaEditando.value?.version_vigente?.configuracion_json || {};
  const columnas = plantillaForm.columnas
    .filter((columna) => columna.campo_destino)
    .map((columna, index) => ({
      campo_destino: columna.campo_destino,
      etiqueta: columna.etiqueta || columna.campo_destino.replace(/_/g, " "),
      origen: columna.origen,
      valor:
        columna.origen === "constante"
          ? parseValorConstantePlantilla(columna.valor)
          : undefined,
      transformacion: columna.transformacion || undefined,
      requerido: columna.requerido,
      ejemplo: columna.ejemplo || undefined,
      letra_columna:
        columna.origen === "columna" && columna.letra_columna
          ? columna.letra_columna
          : undefined,
      indice_columna:
        columna.origen === "columna" && columna.indice_columna
          ? Number(columna.indice_columna)
          : undefined,
      orden: index + 1,
    }));
  const campos = columnas.reduce<Record<string, Record<string, unknown>>>(
    (acc, columna) => {
      const detalle: Record<string, unknown> = {
        origen: columna.origen,
        requerido: columna.requerido,
      };
      if (columna.transformacion) detalle.transformacion = columna.transformacion;
      if (columna.origen === "header") {
        detalle.encabezados = [columna.etiqueta];
      }
      if (columna.origen === "columna") {
        if (columna.letra_columna) detalle.letra_columna = columna.letra_columna;
        if (columna.indice_columna !== undefined) {
          detalle.indice_columna = columna.indice_columna;
        }
      }
      if (columna.origen === "constante") {
        detalle.valor = columna.valor;
      }
      acc[columna.campo_destino] = detalle;
      return acc;
    },
    {},
  );
  return {
    ...configuracionActual,
    tipo: configuracionActual.tipo || "plantilla_visual",
    header_row: configuracionActual.header_row || 1,
    modo_agrupacion: configuracionActual.modo_agrupacion || "fila",
    plantilla: {
      nombre_publico: plantillaForm.nombre,
      columnas,
    },
    campos,
  };
};

const crearPayloadPlantilla = (): FormatoImportacionPayload => ({
  nombre: plantillaForm.nombre.trim(),
  descripcion: plantillaForm.descripcion.trim() || null,
  alcance: plantillaForm.alcance,
  configuracion_json: construirConfiguracionPlantilla(),
});

const crearPayload = (source: typeof form): EmpresaCreate => ({
  razon_social: source.razon_social.trim(),
  cuit: source.cuit.replace(/\D/g, ""),
  condicion_iva: source.condicion_iva as Empresa["condicion_iva"],
  ingresos_brutos: source.ingresos_brutos.trim() || undefined,
  domicilio: source.domicilio.trim(),
  localidad: source.localidad.trim(),
  provincia:
    normalizarProvinciaArgentina(source.provincia) || source.provincia.trim(),
  codigo_postal: source.codigo_postal.trim(),
  email: source.email.trim() || undefined,
  telefono: source.telefono.trim() || undefined,
  inicio_actividades: source.inicio_actividades,
});

const crearPayloadPerfil = (): PerfilCargaMasivaPayload => ({
  nombre: perfilForm.nombre.trim(),
  descripcion: perfilForm.descripcion.trim() || null,
  es_predeterminado: perfilForm.es_predeterminado,
  activo: true,
  configuracion_json: {
    ...(perfilForm.configuracion as PerfilCargaMasivaConfiguracion),
    formato_importacion_version_id:
      Number(perfilForm.configuracion.formato_importacion_version_id || 0) ||
      null,
    punto_venta: {
      modo: perfilForm.configuracion.punto_venta?.modo || "archivo",
      numero:
        Number(perfilForm.configuracion.punto_venta?.numero || 0) || null,
    },
    descripcion_item_fija:
      perfilForm.configuracion.descripcion_item_fija?.trim() || "",
    fecha_vto_pago: {
      ...perfilForm.configuracion.fecha_vto_pago,
      dias: Number(perfilForm.configuracion.fecha_vto_pago.dias || 0),
    },
  },
});

const descripcionPerfil = (perfil: PerfilCargaMasiva) => {
  const config = perfil.configuracion_json;
  const partes = [];
  if (config.concepto_modo) partes.push(`Concepto: ${config.concepto_modo}`);
  if (config.punto_venta?.modo === "fijo" && config.punto_venta.numero) {
    partes.push(`PV: ${String(config.punto_venta.numero).padStart(4, "0")}`);
  } else {
    partes.push("PV desde archivo");
  }
  if (config.descripcion_item_modo === "fija") {
    partes.push(`Descripción: ${config.descripcion_item_fija || "-"}`);
  } else if (config.descripcion_item_modo) {
    partes.push("Descripción desde archivo");
  }
  if (config.fecha_emision?.modo) {
    partes.push(`Emisión: ${config.fecha_emision.modo.replace(/_/g, " ")}`);
  }
  return partes.join(" · ") || "Sin configuración fiscal predefinida";
};

const descripcionPlantilla = (formato: FormatoImportacion) => {
  const version = formato.version_vigente;
  const columnas = (
    version?.configuracion_json?.plantilla as
      | { columnas?: Array<Record<string, unknown>> }
      | undefined
  )?.columnas;
  const campos = version?.configuracion_json?.campos;
  const cantidadCampos =
    campos && typeof campos === "object" && !Array.isArray(campos)
      ? Object.keys(campos).length
      : 0;
  const cantidad = Array.isArray(columnas)
    ? columnas.length
    : cantidadCampos;
  const protegida = esPlantillaProtegida(formato) ? " · Sistema protegido" : "";
  return `Versión ${version?.version || "-"} · ${cantidad} campos · ${etiquetaAlcancePlantilla(formato)}${protegida}`;
};

const actualizarCampoPlantilla = (columna: PlantillaColumnaForm) => {
  const campo = catalogoCampos.value.find(
    (item) => item.codigo === columna.campo_destino,
  );
  if (!campo) return;
  if (!campo.origenes.includes(columna.origen)) {
    columna.origen = (campo.origenes[0] as PlantillaOrigen) || "header";
  }
  if (!columna.etiqueta) {
    columna.etiqueta = campo.etiqueta;
  }
  if (
    columna.transformacion &&
    !campo.transformaciones.includes(columna.transformacion)
  ) {
    columna.transformacion = campo.transformaciones[0] || "";
  }
  if (!columna.transformacion && campo.transformaciones.length > 0) {
    columna.transformacion = campo.transformaciones[0];
  }
  columna.requerido = columna.requerido || campo.requerido_base;
};

const origenesPlantillaOptionsPara = (columna: PlantillaColumnaForm) => {
  const campo = catalogoCampos.value.find(
    (item) => item.codigo === columna.campo_destino,
  );
  const permitidos = campo?.origenes || ["header", "columna", "constante"];
  return origenPlantillaOptions.filter((option) =>
    permitidos.includes(option.value),
  );
};

const transformacionesPlantillaOptionsPara = (columna: PlantillaColumnaForm) => {
  const campo = catalogoCampos.value.find(
    (item) => item.codigo === columna.campo_destino,
  );
  const permitidas = campo?.transformaciones || [];
  return transformacionPlantillaOptions.filter(
    (option) => option.value === "" || permitidas.includes(String(option.value)),
  );
};

const agregarColumnaPlantilla = () => {
  plantillaForm.columnas.push(crearColumnaPlantilla());
};

const quitarColumnaPlantilla = (index: number) => {
  plantillaForm.columnas.splice(index, 1);
};

const moverColumnaPlantilla = (index: number, direction: -1 | 1) => {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= plantillaForm.columnas.length) return;
  const [columna] = plantillaForm.columnas.splice(index, 1);
  plantillaForm.columnas.splice(nextIndex, 0, columna);
};

const abrirCrearPlantilla = () => {
  plantillaEditando.value = null;
  resetPlantillaForm();
  showPlantillaModal.value = true;
  void evaluarCompatibilidadPlantilla();
};

const abrirEditarPlantilla = (formato: FormatoImportacion) => {
  if (!puedeAdministrarPlantilla(formato)) {
    showError(
      "Plantilla no editable",
      formato.alcance === "global"
        ? "Solo un administrador puede editar plantillas globales."
        : "Clona esta plantilla del sistema antes de editarla.",
    );
    return;
  }
  plantillaEditando.value = formato;
  plantillaForm.nombre = formato.nombre;
  plantillaForm.descripcion = formato.descripcion || "";
  plantillaForm.alcance = formato.alcance === "global" ? "global" : "emisor";
  plantillaForm.columnas = columnasDesdeConfiguracion(
    formato.version_vigente?.configuracion_json || {},
  );
  showPlantillaModal.value = true;
  void evaluarCompatibilidadPlantilla();
};

const cerrarPlantillaModal = () => {
  if (savingPlantilla.value) return;
  showPlantillaModal.value = false;
};

const seleccionarExcelPlantilla = () => {
  plantillaExcelInput.value?.click();
};

const procesarExcelPlantilla = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const analisis = await formatosImportacionService.analizarExcel(file);
    plantillaEditando.value = null;
    resetPlantillaForm();
    plantillaForm.nombre = file.name.replace(/\.xlsx$/i, "");
    plantillaForm.columnas = analisis.columnas.map((columna) =>
      crearColumnaPlantilla({
        etiqueta: columna.encabezado,
        origen: "header",
        ejemplo: "",
      }),
    );
    showPlantillaModal.value = true;
    showSuccess(
      "Encabezados detectados",
      "Asigná cada columna a un campo FactuFlow antes de guardar la plantilla.",
    );
    void evaluarCompatibilidadPlantilla();
  } catch (error: any) {
    showError(
      "No se pudo leer el Excel",
      error.response?.data?.detail || "Sube un archivo .xlsx válido.",
    );
  }
};

const evaluarCompatibilidadPlantilla = async () => {
  if (!showPlantillaModal.value && !plantillaForm.nombre) return;
  if (!plantillaForm.columnas.some((columna) => columna.campo_destino)) {
    compatibilidadPlantilla.value = null;
    return;
  }
  evaluandoCompatibilidad.value = true;
  try {
    compatibilidadPlantilla.value =
      await formatosImportacionService.evaluarCompatibilidad(
        construirConfiguracionPlantilla(),
      );
  } catch (error: any) {
    compatibilidadPlantilla.value = null;
    showError(
      "No se pudo evaluar la compatibilidad",
      error.response?.data?.detail || "Revisa la configuración de columnas.",
    );
  } finally {
    evaluandoCompatibilidad.value = false;
  }
};

const guardarPlantilla = async () => {
  if (!plantillaForm.nombre.trim()) {
    showError("Falta el nombre", "La plantilla necesita un nombre visible.");
    return;
  }
  if (!plantillaForm.columnas.some((columna) => columna.campo_destino)) {
    showError(
      "Faltan campos",
      "Asigná al menos una columna a un campo FactuFlow.",
    );
    return;
  }
  savingPlantilla.value = true;
  try {
    const payload = crearPayloadPlantilla();
    const compatibilidad = await formatosImportacionService.evaluarCompatibilidad(
      payload.configuracion_json,
    );
    compatibilidadPlantilla.value = compatibilidad;
    if (compatibilidad.estado === "incompatible") {
      showError(
        "Plantilla incompleta",
        "Revisá los faltantes y conflictos antes de guardar.",
      );
      return;
    }
    if (plantillaEditando.value) {
      await formatosImportacionService.actualizar(
        plantillaEditando.value.id,
        payload,
      );
    } else {
      await formatosImportacionService.crear(payload);
    }
    await cargarConfiguracionCargaMasiva();
    showPlantillaModal.value = false;
    showSuccess(
      "Plantilla guardada",
      "La plantilla quedó disponible para carga masiva.",
    );
  } catch (error: any) {
    showError(
      "No se pudo guardar la plantilla",
      error.response?.data?.detail || "Revisa los datos e intenta nuevamente.",
    );
  } finally {
    savingPlantilla.value = false;
  }
};

const clonarPlantilla = async (formato: FormatoImportacion) => {
  try {
    await formatosImportacionService.clonar(formato.id, {
      nombre: `Copia de ${formato.nombre}`,
      alcance: "emisor",
    });
    await cargarConfiguracionCargaMasiva();
    showSuccess(
      "Plantilla clonada",
      "La copia editable quedó asociada al emisor activo.",
    );
  } catch (error: any) {
    showError(
      "No se pudo clonar la plantilla",
      error.response?.data?.detail || "Intenta nuevamente.",
    );
  }
};

const descargarPlantilla = async (formato: FormatoImportacion) => {
  try {
    const blob = await formatosImportacionService.descargar(formato.id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `plantilla-${formato.nombre.replace(/\W+/g, "-").toLowerCase()}.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    showError(
      "No se pudo descargar la plantilla",
      error.response?.data?.detail || "Intenta nuevamente.",
    );
  }
};

const solicitarEliminarPlantilla = (formato: FormatoImportacion) => {
  plantillaAEliminar.value = formato;
};

const eliminarPlantilla = async () => {
  if (!plantillaAEliminar.value) return;
  try {
    await formatosImportacionService.eliminar(plantillaAEliminar.value.id);
    await cargarConfiguracionCargaMasiva();
    plantillaAEliminar.value = null;
    showSuccess(
      "Plantilla desactivada",
      "La plantilla ya no aparecerá para nuevas cargas masivas.",
    );
  } catch (error: any) {
    showError(
      "No se pudo desactivar la plantilla",
      error.response?.data?.detail || "Intenta nuevamente.",
    );
  }
};

const cargarEmpresa = async () => {
  loading.value = true;

  try {
    if (!empresaStore.empresaActivaId) {
      await empresaStore.inicializarEmpresaActiva();
    } else if (!empresaActiva.value) {
      await empresaStore.fetchEmpresa(empresaStore.empresaActivaId);
    }

    sincronizarFormulario(empresaActiva.value);
  } catch (error: any) {
    showError(
      "No se pudo cargar el emisor",
      error.response?.data?.detail || "Revisa tu sesión e intenta nuevamente.",
    );
  } finally {
    loading.value = false;
  }
};

const cargarConfiguracionCargaMasiva = async () => {
  if (!empresaStore.empresaActivaId) return;

  loadingPerfiles.value = true;
  try {
    const [perfiles, formatos, puntos, campos] = await Promise.all([
      perfilesCargaMasivaService.listar(),
      formatosImportacionService.listar(),
      puntosVentaService.getAll(),
      formatosImportacionService.catalogoCampos(),
    ]);
    perfilesCargaMasiva.value = perfiles;
    formatosImportacion.value = formatos;
    puntosVenta.value = puntos;
    catalogoCampos.value = campos;
  } catch (error: any) {
    showError(
      "No se pudo cargar la configuración de carga masiva",
      error.response?.data?.detail ||
        "Revisa tu sesión e intenta nuevamente.",
    );
  } finally {
    loadingPerfiles.value = false;
  }
};

const guardarEmpresa = async () => {
  if (!empresaActiva.value) return;

  saving.value = true;

  try {
    const payload: EmpresaUpdate = crearPayload(form);

    await empresaStore.updateEmpresa(empresaActiva.value.id, payload);
    showSuccess(
      "Emisor actualizado",
      "Los datos fiscales del emisor activo se guardaron correctamente.",
    );
  } catch (error: any) {
    showError(
      "No se pudo guardar el emisor",
      error.response?.data?.detail || "Corrige los datos e intenta nuevamente.",
    );
  } finally {
    saving.value = false;
  }
};

const abrirCrearEmisor = () => {
  resetCreateForm();
  extractionWarnings.value = [];
  showCreateModal.value = true;
};

const cerrarCrearEmisor = () => {
  if (creating.value) return;
  showCreateModal.value = false;
};

const crearEmisor = async () => {
  creating.value = true;

  try {
    const nuevoEmisor = await empresaStore.createEmpresa(
      crearPayload(createForm),
    );
    await empresaStore.fetchEmpresas();
    await empresaStore.setEmpresaActiva(nuevoEmisor.id);
    sincronizarFormulario(nuevoEmisor);
    showCreateModal.value = false;
    showSuccess(
      "Emisor agregado",
      "El nuevo emisor quedó seleccionado como activo.",
    );
  } catch (error: any) {
    showError(
      "No se pudo agregar el emisor",
      error.response?.data?.detail || "Corrige los datos e intenta nuevamente.",
    );
  } finally {
    creating.value = false;
  }
};

const abrirCrearPerfil = () => {
  perfilEditando.value = null;
  resetPerfilForm();
  showPerfilModal.value = true;
};

const abrirEditarPerfil = (perfil: PerfilCargaMasiva) => {
  perfilEditando.value = perfil;
  sincronizarPerfilForm(perfil);
  showPerfilModal.value = true;
};

const cerrarPerfilModal = () => {
  if (savingPerfil.value) return;
  showPerfilModal.value = false;
};

const guardarPerfil = async () => {
  savingPerfil.value = true;
  try {
    const payload = crearPayloadPerfil();
    if (perfilEditando.value) {
      await perfilesCargaMasivaService.actualizar(
        perfilEditando.value.id,
        payload,
      );
    } else {
      await perfilesCargaMasivaService.crear(payload);
    }
    await cargarConfiguracionCargaMasiva();
    showPerfilModal.value = false;
    showSuccess(
      "Perfil de carga masiva guardado",
      "La configuración quedó disponible para el emisor activo.",
    );
  } catch (error: any) {
    showError(
      "No se pudo guardar el perfil de carga masiva",
      error.response?.data?.detail || "Revisa los datos e intenta nuevamente.",
    );
  } finally {
    savingPerfil.value = false;
  }
};

const marcarPerfilPredeterminado = async (perfil: PerfilCargaMasiva) => {
  try {
    await perfilesCargaMasivaService.marcarPredeterminado(perfil.id);
    await cargarConfiguracionCargaMasiva();
    showSuccess(
      "Perfil de carga masiva predeterminado actualizado",
      "Este perfil de carga masiva se aplicará al entrar en Emisión masiva.",
    );
  } catch (error: any) {
    showError(
      "No se pudo marcar el perfil de carga masiva",
      error.response?.data?.detail || "Intenta nuevamente.",
    );
  }
};

const solicitarEliminarPerfil = (perfil: PerfilCargaMasiva) => {
  perfilAEliminar.value = perfil;
};

const eliminarPerfil = async () => {
  if (!perfilAEliminar.value) return;
  try {
    await perfilesCargaMasivaService.eliminar(perfilAEliminar.value.id);
    await cargarConfiguracionCargaMasiva();
    perfilAEliminar.value = null;
    showSuccess(
      "Perfil de carga masiva eliminado",
      "El emisor activo ya no usará esa configuración.",
    );
  } catch (error: any) {
    showError(
      "No se pudo eliminar el perfil de carga masiva",
      error.response?.data?.detail || "Intenta nuevamente.",
    );
  }
};

const seleccionarConstancia = () => {
  constanciaInput.value?.click();
};

const aplicarValorExtraido = (
  field: keyof typeof createForm,
  value: string | null,
) => {
  if (value) {
    createForm[field] = value;
  }
};

const procesarConstancia = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";

  if (!file) return;

  extractionWarnings.value = [];
  extractingConstancia.value = true;

  try {
    const datos = await empresaService.extraerConstancia(file);
    aplicarValorExtraido("razon_social", datos.razon_social);
    aplicarValorExtraido("cuit", datos.cuit);
    aplicarValorExtraido("condicion_iva", datos.condicion_iva);
    aplicarValorExtraido("domicilio", datos.domicilio);
    aplicarValorExtraido("localidad", datos.localidad);
    if (esProvinciaArgentina(datos.provincia)) {
      aplicarValorExtraido(
        "provincia",
        normalizarProvinciaArgentina(datos.provincia),
      );
    }
    aplicarValorExtraido("codigo_postal", datos.codigo_postal);
    aplicarValorExtraido("inicio_actividades", datos.inicio_actividades);
    extractionWarnings.value = datos.warnings || [];
    showSuccess(
      "Constancia procesada",
      "Revisa los datos detectados antes de guardar el emisor.",
    );
  } catch (error: any) {
    showError(
      "No se pudo procesar la constancia",
      error.response?.data?.detail || "Sube una constancia ARCA en PDF.",
    );
  } finally {
    extractingConstancia.value = false;
  }
};

watch(
  () => ({
    visible: showPlantillaModal.value,
    nombre: plantillaForm.nombre,
    alcance: plantillaForm.alcance,
    columnas: plantillaForm.columnas.map((columna) => ({ ...columna })),
  }),
  () => {
    if (!showPlantillaModal.value) return;
    if (compatibilidadPlantillaTimer) {
      clearTimeout(compatibilidadPlantillaTimer);
    }
    compatibilidadPlantillaTimer = setTimeout(() => {
      void evaluarCompatibilidadPlantilla();
    }, 450);
  },
  { deep: true },
);

watch(empresaActiva, (empresa) => {
  sincronizarFormulario(empresa);
  cargarConfiguracionCargaMasiva();
});

onMounted(async () => {
  await cargarEmpresa();
  await cargarConfiguracionCargaMasiva();
});
</script>

<template>
  <div class="space-y-6">
    <div
      class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"
    >
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          Emisores
        </h1>
        <p class="mt-2 max-w-3xl text-gray-600">
          Administra los datos fiscales de las personas o razones sociales que
          emiten comprobantes.
        </p>
      </div>

      <div class="flex flex-wrap gap-3">
        <BaseButton
          variant="secondary"
          class="gap-2"
          @click="abrirCrearEmisor"
        >
          <PlusIcon class="h-5 w-5" />
          Agregar emisor
        </BaseButton>
        <BaseButton
          :loading="saving"
          :disabled="!empresaActiva"
          @click="guardarEmpresa"
        >
          Guardar cambios
        </BaseButton>
      </div>
    </div>

    <BaseAlert type="info">
      Los cambios impactan en el emisor activo seleccionado y se reflejan en la
      operatoria diaria.
    </BaseAlert>

    <div class="border-b border-gray-200">
      <nav
        class="-mb-px flex gap-6"
        aria-label="Secciones de emisor"
      >
        <button
          type="button"
          :class="[
            'border-b-2 px-1 py-3 text-sm font-medium',
            activeTab === 'datos'
              ? 'border-primary-600 text-primary-700'
              : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
          ]"
          @click="activeTab = 'datos'"
        >
          Datos del emisor
        </button>
        <button
          type="button"
          :class="[
            'border-b-2 px-1 py-3 text-sm font-medium',
            activeTab === 'carga-masiva'
              ? 'border-primary-600 text-primary-700'
              : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
          ]"
          @click="activeTab = 'carga-masiva'"
        >
          Carga masiva
        </button>
      </nav>
    </div>

    <div
      v-if="loading"
      class="flex justify-center py-16"
    >
      <BaseSpinner size="lg" />
    </div>

    <template v-else-if="empresaActiva">
      <div
        v-if="activeTab === 'datos'"
        class="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]"
      >
        <BaseCard title="Datos principales">
          <div class="grid gap-4 md:grid-cols-2">
            <BaseInput
              v-model="form.razon_social"
              label="Razón social"
              required
            />
            <BaseInput
              v-model="form.cuit"
              label="CUIT"
              hint="Ingresalo sin guiones."
              required
            />
            <BaseSelect
              v-model="form.condicion_iva"
              :options="condicionIvaOptions"
              label="Condición IVA"
              required
            />
            <BaseInput
              v-model="form.ingresos_brutos"
              label="Ingresos Brutos"
              placeholder="Ej.: CM 12345678 o Exento"
            />
            <BaseInput
              v-model="form.inicio_actividades"
              type="date"
              label="Inicio de actividades"
              required
            />
            <div class="md:col-span-2">
              <BaseInput
                v-model="form.domicilio"
                label="Domicilio fiscal"
                required
              />
            </div>
            <BaseInput
              v-model="form.localidad"
              label="Localidad"
              required
            />
            <BaseSelect
              v-model="form.provincia"
              label="Provincia"
              :options="provinciasOptions"
              required
            />
            <BaseInput
              v-model="form.codigo_postal"
              label="Código postal"
              required
            />
            <BaseInput
              v-model="form.telefono"
              label="Teléfono"
              type="tel"
            />
            <div class="md:col-span-2">
              <BaseInput
                v-model="form.email"
                label="Email de contacto"
                type="email"
              />
            </div>
          </div>
        </BaseCard>

        <div class="space-y-6">
          <BaseCard title="Resumen operativo">
            <div class="space-y-4">
              <div class="flex items-start gap-3">
                <div class="rounded-xl bg-blue-50 p-3 text-blue-600">
                  <BuildingOffice2Icon class="h-5 w-5" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">
                    Emisor activo
                  </p>
                  <p class="font-semibold text-gray-900">
                    {{ empresaActiva.razon_social }}
                  </p>
                </div>
              </div>

              <div class="flex items-start gap-3">
                <div class="rounded-xl bg-emerald-50 p-3 text-emerald-600">
                  <IdentificationIcon class="h-5 w-5" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">
                    CUIT
                  </p>
                  <p class="font-semibold text-gray-900">
                    {{ empresaActiva.cuit }}
                  </p>
                </div>
              </div>

              <div class="flex items-start gap-3">
                <div class="rounded-xl bg-amber-50 p-3 text-amber-600">
                  <CalendarDaysIcon class="h-5 w-5" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">
                    Última actualización
                  </p>
                  <p class="font-semibold text-gray-900">
                    {{
                      new Date(empresaActiva.updated_at).toLocaleString("es-AR")
                    }}
                  </p>
                </div>
              </div>
            </div>
          </BaseCard>

          <BaseCard title="Qué conviene revisar">
            <ul class="space-y-3 text-sm text-gray-600">
              <li>
                Confirma que el CUIT coincida con el emisor activo y con el
                certificado productivo que vayas a usar.
              </li>
              <li>
                Si el emisor es una persona física, usa su nombre fiscal tal
                como figura en ARCA.
              </li>
              <li>
                Verifica domicilio, condición IVA y fecha de inicio antes de
                generar comprobantes reales.
              </li>
              <li>
                Si cambias datos fiscales sensibles, vuelve a controlar PDFs,
                reportes y puntos de venta.
              </li>
            </ul>
          </BaseCard>
        </div>
      </div>

      <div
        v-else
        class="space-y-6"
      >
        <div class="flex flex-wrap gap-2 rounded-lg border border-gray-200 bg-white p-1">
          <button
            type="button"
            :class="[
              'rounded-md px-4 py-2 text-sm font-medium',
              cargaMasivaTab === 'perfiles'
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-600 hover:bg-gray-50',
            ]"
            @click="cargaMasivaTab = 'perfiles'"
          >
            Perfiles
          </button>
          <button
            type="button"
            :class="[
              'rounded-md px-4 py-2 text-sm font-medium',
              cargaMasivaTab === 'plantillas'
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-600 hover:bg-gray-50',
            ]"
            @click="cargaMasivaTab = 'plantillas'"
          >
            Plantillas
          </button>
        </div>

        <div
          v-if="cargaMasivaTab === 'perfiles'"
          class="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]"
        >
          <BaseCard title="Perfiles de carga masiva">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <p class="text-sm text-gray-600">
                Configura valores habituales para precargar Emisión masiva. El
                usuario siempre podrá revisar y editar todo antes de validar.
              </p>
              <BaseButton
                class="gap-2"
                @click="abrirCrearPerfil"
              >
                <PlusIcon class="h-5 w-5" />
                Nuevo perfil
              </BaseButton>
            </div>

            <div
              v-if="loadingPerfiles"
              class="flex justify-center py-10"
            >
              <BaseSpinner />
            </div>

            <div
              v-else-if="perfilesCargaMasiva.length > 0"
              class="mt-5 divide-y divide-gray-200 rounded-lg border border-gray-200"
            >
              <div
                v-for="perfil in perfilesCargaMasiva"
                :key="perfil.id"
                class="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between"
              >
                <div>
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="font-semibold text-gray-900">
                      {{ perfil.nombre }}
                    </p>
                    <span
                      v-if="perfil.es_predeterminado"
                      class="rounded-full bg-primary-50 px-2 py-1 text-xs font-semibold text-primary-700"
                    >
                      Predeterminado
                    </span>
                  </div>
                  <p class="mt-1 text-sm text-gray-600">
                    {{ perfil.descripcion || descripcionPerfil(perfil) }}
                  </p>
                  <p class="mt-1 text-xs text-gray-500">
                    {{ descripcionPerfil(perfil) }}
                  </p>
                </div>

                <div class="flex flex-wrap gap-2">
                  <BaseButton
                    v-if="!perfil.es_predeterminado"
                    size="sm"
                    variant="secondary"
                    @click="marcarPerfilPredeterminado(perfil)"
                  >
                    <StarIcon class="mr-2 h-4 w-4" />
                    Predeterminar
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    @click="abrirEditarPerfil(perfil)"
                  >
                    <PencilSquareIcon class="mr-2 h-4 w-4" />
                    Editar
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="danger"
                    @click="solicitarEliminarPerfil(perfil)"
                  >
                    <TrashIcon class="mr-2 h-4 w-4" />
                    Eliminar
                  </BaseButton>
                </div>
              </div>
            </div>

            <BaseAlert
              v-else
              type="info"
              class="mt-5"
            >
              Todavía no hay perfiles de carga masiva para este emisor. Cuando
              crees uno, Emisión masiva podrá aplicarlo automáticamente.
            </BaseAlert>
          </BaseCard>

          <BaseCard title="Cómo se usa">
            <ul class="space-y-3 text-sm text-gray-600">
              <li>
                Si el emisor tiene un solo perfil de carga masiva, se aplica al
                entrar en Emisión masiva.
              </li>
              <li>
                Si tiene varios, se aplica el predeterminado. Si no hay
                predeterminado, el usuario elige uno.
              </li>
              <li>
                Las fechas relativas se resuelven en la pantalla de carga y
                quedan editables antes de validar.
              </li>
              <li>
                El perfil de carga masiva no emite ni valida automáticamente;
                solo completa la pantalla.
              </li>
            </ul>
          </BaseCard>
        </div>

        <div
          v-else
          class="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]"
        >
          <BaseCard title="Plantillas de carga masiva">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <p class="text-sm text-gray-600">
                Crea archivos Excel simples para cada emisor. Los
                administradores también pueden definir plantillas globales. Las
                plantillas del sistema se pueden clonar, pero no editar
                directamente.
              </p>
              <div class="flex flex-wrap gap-2">
                <BaseButton
                  variant="secondary"
                  class="gap-2"
                  @click="seleccionarExcelPlantilla"
                >
                  <DocumentArrowUpIcon class="h-5 w-5" />
                  Desde Excel
                </BaseButton>
                <BaseButton
                  class="gap-2"
                  @click="abrirCrearPlantilla"
                >
                  <PlusIcon class="h-5 w-5" />
                  Nueva plantilla
                </BaseButton>
              </div>
              <input
                ref="plantillaExcelInput"
                class="hidden"
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                @change="procesarExcelPlantilla"
              >
            </div>

            <div
              v-if="loadingPerfiles"
              class="flex justify-center py-10"
            >
              <BaseSpinner />
            </div>

            <div
              v-else-if="plantillasDisponibles.length > 0"
              class="mt-5 divide-y divide-gray-200 rounded-lg border border-gray-200"
            >
              <div
                v-for="plantilla in plantillasDisponibles"
                :key="plantilla.id"
                class="flex flex-col gap-4 p-4 xl:flex-row xl:items-center xl:justify-between"
              >
                <div>
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="font-semibold text-gray-900">
                      {{ plantilla.nombre }}
                    </p>
                    <span class="rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-700">
                      {{ etiquetaAlcancePlantilla(plantilla) }}
                    </span>
                    <span
                      v-if="esPlantillaProtegida(plantilla)"
                      class="rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700"
                    >
                      Sistema
                    </span>
                  </div>
                  <p class="mt-1 text-sm text-gray-600">
                    {{ plantilla.descripcion || descripcionPlantilla(plantilla) }}
                  </p>
                  <p class="mt-1 text-xs text-gray-500">
                    {{ descripcionPlantilla(plantilla) }}
                  </p>
                </div>

                <div class="flex flex-wrap gap-2">
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    @click="descargarPlantilla(plantilla)"
                  >
                    <ArrowDownTrayIcon class="mr-2 h-4 w-4" />
                    Descargar
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    @click="clonarPlantilla(plantilla)"
                  >
                    <DocumentDuplicateIcon class="mr-2 h-4 w-4" />
                    Clonar
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    :disabled="!puedeAdministrarPlantilla(plantilla)"
                    @click="abrirEditarPlantilla(plantilla)"
                  >
                    <PencilSquareIcon class="mr-2 h-4 w-4" />
                    Editar
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="danger"
                    :disabled="!puedeAdministrarPlantilla(plantilla)"
                    @click="solicitarEliminarPlantilla(plantilla)"
                  >
                    <TrashIcon class="mr-2 h-4 w-4" />
                    Desactivar
                  </BaseButton>
                </div>
              </div>
            </div>

            <BaseAlert
              v-else
              type="info"
              class="mt-5"
            >
              Todavía no hay plantillas configuradas. Puedes empezar desde cero
              o subir un Excel de ejemplo para tomar sus encabezados.
            </BaseAlert>
          </BaseCard>

          <BaseCard title="Compatibilidad fiscal">
            <ul class="space-y-3 text-sm text-gray-600">
              <li>
                La plantilla define qué columnas existen; el perfil define qué
                datos pueden quedar fijos o precargados.
              </li>
              <li>
                Si el perfil exige datos desde archivo, la plantilla debe tener
                esas columnas.
              </li>
              <li>
                Las notas de crédito y débito requieren comprobante asociado
                antes de poder emitir.
              </li>
              <li>
                La fecha de emisión nunca se completa con la fecha del día por
                defecto.
              </li>
            </ul>
          </BaseCard>
        </div>
      </div>
    </template>

    <BaseAlert
      v-else
      type="warning"
    >
      No hay un emisor seleccionado. Agrega un emisor para empezar a configurar
      certificados, puntos de venta y comprobantes.
    </BaseAlert>

    <BaseModal
      :show="showCreateModal"
      title="Agregar emisor"
      size="xl"
      @close="cerrarCrearEmisor"
    >
      <form
        class="space-y-5"
        @submit.prevent="crearEmisor"
      >
        <BaseAlert type="info">
          Agrega una persona o razon social que va a emitir comprobantes. Puedes
          cargar una constancia ARCA para completar los datos principales y
          editarlos antes de guardar.
        </BaseAlert>

        <div
          class="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4"
        >
          <div
            class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
          >
            <div>
              <p class="font-medium text-gray-900">
                Completar desde constancia ARCA
              </p>
              <p class="mt-1 text-sm text-gray-600">
                Sube el PDF de constancia de inscripción. FactuFlow completa los
                campos detectados y deja el formulario editable.
              </p>
            </div>
            <BaseButton
              variant="secondary"
              class="gap-2"
              :loading="extractingConstancia"
              :disabled="creating"
              @click="seleccionarConstancia"
            >
              <DocumentArrowUpIcon class="h-5 w-5" />
              Subir constancia
            </BaseButton>
          </div>
          <input
            ref="constanciaInput"
            class="hidden"
            type="file"
            accept="application/pdf,.pdf"
            @change="procesarConstancia"
          >
        </div>

        <BaseAlert
          v-if="extractionWarnings.length > 0"
          type="warning"
        >
          <p class="mb-2 font-medium">
            Revisa estos datos manualmente:
          </p>
          <ul class="list-disc space-y-1 pl-5">
            <li
              v-for="warning in extractionWarnings"
              :key="warning"
            >
              {{ warning }}
            </li>
          </ul>
        </BaseAlert>

        <div class="grid gap-4 md:grid-cols-2">
          <BaseInput
            v-model="createForm.razon_social"
            label="Nombre fiscal / razón social"
            required
          />
          <BaseInput
            v-model="createForm.cuit"
            label="CUIT"
            hint="Ingresalo sin guiones."
            required
          />
          <BaseSelect
            v-model="createForm.condicion_iva"
            :options="condicionIvaOptions"
            label="Condición IVA"
            required
          />
          <BaseInput
            v-model="createForm.ingresos_brutos"
            label="Ingresos Brutos"
            placeholder="Ej.: CM 12345678 o Exento"
          />
          <BaseInput
            v-model="createForm.inicio_actividades"
            type="date"
            label="Inicio de actividades"
            required
          />
          <div class="md:col-span-2">
            <BaseInput
              v-model="createForm.domicilio"
              label="Domicilio fiscal"
              required
            />
          </div>
          <BaseInput
            v-model="createForm.localidad"
            label="Localidad"
            required
          />
          <BaseSelect
            v-model="createForm.provincia"
            label="Provincia"
            :options="provinciasOptions"
            required
          />
          <BaseInput
            v-model="createForm.codigo_postal"
            label="Código postal"
            required
          />
          <BaseInput
            v-model="createForm.telefono"
            label="Teléfono"
            type="tel"
          />
          <div class="md:col-span-2">
            <BaseInput
              v-model="createForm.email"
              label="Email de contacto"
              type="email"
            />
          </div>
        </div>

        <div class="flex justify-end gap-3 border-t border-gray-200 pt-5">
          <BaseButton
            variant="secondary"
            :disabled="creating"
            @click="cerrarCrearEmisor"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            type="submit"
            :loading="creating"
          >
            Agregar y seleccionar emisor
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showPerfilModal"
      :title="
        perfilEditando
          ? 'Editar perfil de carga masiva'
          : 'Nuevo perfil de carga masiva'
      "
      size="xl"
      @close="cerrarPerfilModal"
    >
      <form
        class="space-y-5"
        @submit.prevent="guardarPerfil"
      >
        <BaseAlert type="info">
          El perfil solo precarga la pantalla de Emisión masiva. Las fechas,
          punto de venta, concepto fiscal ARCA y descripción facturada quedan
          visibles y editables antes de validar.
        </BaseAlert>

        <div class="grid gap-4 md:grid-cols-2">
          <BaseInput
            v-model="perfilForm.nombre"
            label="Nombre"
            required
          />
          <BaseSelect
            v-model="perfilFormatoImportacionVersionId"
            :options="formatosOptions"
            label="Plantilla opcional"
          />
          <BaseSelect
            v-model="perfilPuntoVentaSeleccionado"
            :options="puntoVentaPerfilOptions"
            label="Punto de venta"
          />
          <div class="md:col-span-2">
            <BaseInput
              v-model="perfilForm.descripcion"
              label="Descripción interna"
            />
          </div>
          <BaseAlert
            v-if="puntosVentaFactuflow.length === 0"
            type="warning"
            class="md:col-span-2"
          >
            Para elegir un punto de venta fijo, primero cargá los puntos de
            venta habilitados del emisor en la pantalla Puntos de venta.
          </BaseAlert>
          <BaseSelect
            v-model="perfilForm.configuracion.concepto_modo"
            :options="conceptoPerfilOptions"
            label="Concepto fiscal ARCA"
          />
          <BaseSelect
            v-model="perfilForm.configuracion.descripcion_item_modo"
            :options="descripcionPerfilOptions"
            label="Descripción facturada"
          />
          <div
            v-if="perfilForm.configuracion.descripcion_item_modo === 'fija'"
            class="md:col-span-2"
          >
            <BaseInput
              v-model="perfilForm.configuracion.descripcion_item_fija"
              label="Texto de descripción fija"
              placeholder="Ej.: Ajuste"
            />
          </div>
        </div>

        <div class="grid gap-4 lg:grid-cols-3">
          <BaseSelect
            v-model="perfilForm.configuracion.fecha_emision.modo"
            :options="fechaEmisionPerfilOptions"
            label="Fecha de emisión"
          />
          <BaseInput
            v-if="perfilForm.configuracion.fecha_emision.modo === 'personalizada'"
            v-model="perfilForm.configuracion.fecha_emision.fecha"
            type="date"
            label="Fecha personalizada"
          />
          <BaseSelect
            v-model="perfilForm.configuracion.periodo_servicio.modo"
            :options="periodoPerfilOptions"
            label="Periodo de servicios"
          />
          <BaseInput
            v-if="perfilForm.configuracion.periodo_servicio.modo === 'personalizado'"
            v-model="perfilForm.configuracion.periodo_servicio.desde"
            type="date"
            label="Desde"
          />
          <BaseInput
            v-if="perfilForm.configuracion.periodo_servicio.modo === 'personalizado'"
            v-model="perfilForm.configuracion.periodo_servicio.hasta"
            type="date"
            label="Hasta"
          />
          <BaseSelect
            v-model="perfilForm.configuracion.fecha_vto_pago.modo"
            :options="vencimientoPerfilOptions"
            label="Vencimiento de pago"
          />
          <BaseInput
            v-if="perfilForm.configuracion.fecha_vto_pago.modo === 'emision_mas_dias'"
            v-model="perfilForm.configuracion.fecha_vto_pago.dias"
            type="number"
            min="0"
            label="Días desde emisión"
          />
          <BaseInput
            v-if="perfilForm.configuracion.fecha_vto_pago.modo === 'personalizada'"
            v-model="perfilForm.configuracion.fecha_vto_pago.fecha"
            type="date"
            label="Fecha de vencimiento"
          />
        </div>

        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input
            v-model="perfilForm.es_predeterminado"
            type="checkbox"
            class="h-4 w-4 rounded border-gray-300 text-primary-600"
          >
          Usar como perfil de carga masiva predeterminado del emisor
        </label>

        <div class="flex justify-end gap-3 border-t border-gray-200 pt-5">
          <BaseButton
            variant="secondary"
            :disabled="savingPerfil"
            @click="cerrarPerfilModal"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            type="submit"
            :loading="savingPerfil"
          >
            Guardar perfil
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showPlantillaModal"
      :title="plantillaEditando ? 'Editar plantilla' : 'Nueva plantilla'"
      size="full"
      @close="cerrarPlantillaModal"
    >
      <form
        class="space-y-5"
        @submit.prevent="guardarPlantilla"
      >
        <BaseAlert type="info">
          La plantilla solo define el Excel y su lectura. La emisión masiva
          seguirá mostrando perfil, punto de venta, concepto, fechas y
          confirmación fiscal antes de emitir.
        </BaseAlert>

        <div class="grid gap-4 md:grid-cols-3">
          <BaseInput
            v-model="plantillaForm.nombre"
            label="Nombre de plantilla"
            required
          />
          <BaseSelect
            v-model="plantillaForm.alcance"
            :options="alcancePlantillaOptions"
            label="Alcance"
            :disabled="Boolean(plantillaEditando)"
          />
          <p
            v-if="plantillaEditando"
            class="self-end text-sm text-gray-500"
          >
            Para cambiar el alcance, cloná la plantilla.
          </p>
          <div class="md:col-span-3">
            <BaseInput
              v-model="plantillaForm.descripcion"
              label="Descripción interna"
            />
          </div>
        </div>

        <div class="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div class="min-w-0 space-y-3">
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p class="font-semibold text-gray-900">
                  Columnas y valores
                </p>
                <p class="text-sm text-gray-600">
                  Ordena las filas como quieras que aparezcan en el Excel.
                </p>
              </div>
              <BaseButton
                type="button"
                size="sm"
                variant="secondary"
                class="gap-2"
                @click="agregarColumnaPlantilla"
              >
                <PlusIcon class="h-4 w-4" />
                Agregar columna
              </BaseButton>
            </div>

            <div class="max-h-[48vh] overflow-auto rounded-lg border border-gray-200 bg-white">
              <table class="min-w-[980px] divide-y divide-gray-200 text-sm">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Orden
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Etiqueta
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Campo FactuFlow
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Origen
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Valor / columna
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Transformación
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Requerido
                    </th>
                    <th class="px-3 py-2 text-left font-medium text-gray-600">
                      Ejemplo
                    </th>
                    <th class="px-3 py-2" />
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 bg-white">
                  <tr
                    v-for="(columna, index) in plantillaForm.columnas"
                    :key="columna.id"
                  >
                    <td class="whitespace-nowrap px-3 py-2">
                      <div class="flex gap-1">
                        <button
                          type="button"
                          class="rounded-md p-1 text-gray-500 hover:bg-gray-100"
                          :disabled="index === 0"
                          title="Subir"
                          @click="moverColumnaPlantilla(index, -1)"
                        >
                          <ArrowUpIcon class="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          class="rounded-md p-1 text-gray-500 hover:bg-gray-100"
                          :disabled="index === plantillaForm.columnas.length - 1"
                          title="Bajar"
                          @click="moverColumnaPlantilla(index, 1)"
                        >
                          <ArrowDownIcon class="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                    <td class="min-w-[130px] px-3 py-2">
                      <input
                        v-model="columna.etiqueta"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                        placeholder="Ej.: Fecha emisión"
                      >
                    </td>
                    <td class="min-w-[190px] px-3 py-2">
                      <select
                        v-model="columna.campo_destino"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                        @change="actualizarCampoPlantilla(columna)"
                      >
                        <option
                          v-for="option in camposCatalogoOptions"
                          :key="String(option.value)"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </td>
                    <td class="min-w-[130px] px-3 py-2">
                      <select
                        v-model="columna.origen"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                      >
                        <option
                          v-for="option in origenesPlantillaOptionsPara(columna)"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </td>
                    <td class="min-w-[120px] px-3 py-2">
                      <input
                        v-if="columna.origen === 'constante'"
                        v-model="columna.valor"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                        placeholder="Valor fijo"
                      >
                      <input
                        v-else-if="columna.origen === 'columna'"
                        v-model="columna.letra_columna"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                        placeholder="Ej.: A"
                      >
                      <span
                        v-else-if="columna.origen === 'empresa'"
                        class="text-xs text-gray-500"
                      >
                        Se toma del emisor activo
                      </span>
                      <span
                        v-else
                        class="text-xs text-gray-500"
                      >
                        Usa la etiqueta visible
                      </span>
                    </td>
                    <td class="min-w-[140px] px-3 py-2">
                      <select
                        v-model="columna.transformacion"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                      >
                        <option
                          v-for="option in transformacionesPlantillaOptionsPara(columna)"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                    </td>
                    <td class="px-3 py-2">
                      <input
                        v-model="columna.requerido"
                        type="checkbox"
                        class="h-4 w-4 rounded border-gray-300 text-primary-600"
                      >
                    </td>
                    <td class="min-w-[120px] px-3 py-2">
                      <input
                        v-model="columna.ejemplo"
                        class="w-full rounded-md border border-gray-300 px-2 py-1"
                        placeholder="Ejemplo"
                      >
                    </td>
                    <td class="px-3 py-2">
                      <button
                        type="button"
                        class="rounded-md p-1 text-red-600 hover:bg-red-50"
                        title="Quitar"
                        @click="quitarColumnaPlantilla(index)"
                      >
                        <TrashIcon class="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <aside class="space-y-3 rounded-lg border border-gray-200 bg-gray-50 p-4 xl:max-h-[48vh] xl:overflow-y-auto">
            <div class="flex items-center justify-between gap-3">
              <p class="font-semibold text-gray-900">
                Compatibilidad
              </p>
              <BaseButton
                type="button"
                size="sm"
                variant="secondary"
                :loading="evaluandoCompatibilidad"
                @click="evaluarCompatibilidadPlantilla"
              >
                Revisar
              </BaseButton>
            </div>

            <div
              v-if="compatibilidadPlantilla"
              class="space-y-3"
            >
              <div
                :class="[
                  'flex items-start gap-2 rounded-md px-3 py-2 text-sm',
                  compatibilidadPlantilla.estado === 'incompatible'
                    ? 'bg-red-50 text-red-700'
                    : compatibilidadPlantilla.estado === 'advertencia'
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-emerald-50 text-emerald-700',
                ]"
              >
                <ExclamationTriangleIcon
                  v-if="compatibilidadPlantilla.estado !== 'compatible'"
                  class="mt-0.5 h-5 w-5 flex-none"
                />
                <CheckCircleIcon
                  v-else
                  class="mt-0.5 h-5 w-5 flex-none"
                />
                <span>
                  {{
                    compatibilidadPlantilla.estado === "compatible"
                      ? "La plantilla es compatible con el emisor activo."
                      : compatibilidadPlantilla.estado === "advertencia"
                        ? "La plantilla puede usarse, pero requiere revisión."
                        : "Hay conflictos que deben resolverse."
                  }}
                </span>
              </div>

              <div
                v-for="grupo in [
                  { titulo: 'Conflictos', items: compatibilidadPlantilla.conflictos },
                  { titulo: 'Faltantes', items: compatibilidadPlantilla.faltantes },
                  { titulo: 'Advertencias', items: compatibilidadPlantilla.advertencias },
                  { titulo: 'Omitibles', items: compatibilidadPlantilla.omitibles },
                ]"
                :key="grupo.titulo"
              >
                <div v-if="grupo.items.length > 0">
                  <p class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {{ grupo.titulo }}
                  </p>
                  <ul class="space-y-1 text-sm text-gray-700">
                    <li
                      v-for="mensaje in grupo.items"
                      :key="mensaje.codigo + mensaje.mensaje"
                      class="rounded-md bg-white px-3 py-2"
                    >
                      {{ mensaje.mensaje }}
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <BaseAlert
              v-else
              type="info"
            >
              Asigna campos FactuFlow para ver qué falta o qué puede omitirse
              según el emisor activo.
            </BaseAlert>
          </aside>
        </div>

        <div class="flex justify-end gap-3 border-t border-gray-200 pt-5">
          <BaseButton
            variant="secondary"
            :disabled="savingPlantilla"
            @click="cerrarPlantillaModal"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            type="submit"
            :loading="savingPlantilla"
          >
            Guardar plantilla
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <ConfirmDialog
      :show="!!perfilAEliminar"
      title="Eliminar perfil de carga masiva"
      :message="`¿Eliminar el perfil de carga masiva ${perfilAEliminar?.nombre || ''}?`"
      confirm-text="Eliminar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="eliminarPerfil"
      @cancel="perfilAEliminar = null"
    />

    <ConfirmDialog
      :show="!!plantillaAEliminar"
      title="Desactivar plantilla"
      :message="`¿Desactivar la plantilla ${plantillaAEliminar?.nombre || ''}? No se borrarán versiones históricas usadas por lotes.`"
      confirm-text="Desactivar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="eliminarPlantilla"
      @cancel="plantillaAEliminar = null"
    />
  </div>
</template>
