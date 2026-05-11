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
import { useEmpresaStore } from "@/stores/empresa";
import type { FormatoImportacion } from "@/types/formato-importacion";
import type { Empresa, EmpresaCreate, EmpresaUpdate } from "@/types/empresa";
import type {
  PerfilCargaMasiva,
  PerfilCargaMasivaConfiguracion,
  PerfilCargaMasivaPayload,
} from "@/types/perfil-carga-masiva";
import type { PuntoVenta } from "@/types/punto_venta";
import { configuracionPerfilVacia } from "@/utils/perfiles-carga-masiva";
import {
  BuildingOffice2Icon,
  CalendarDaysIcon,
  DocumentArrowUpIcon,
  IdentificationIcon,
  PencilSquareIcon,
  PlusIcon,
  StarIcon,
  TrashIcon,
} from "@heroicons/vue/24/outline";
import { empresaService } from "@/services/empresa.service";

const empresaStore = useEmpresaStore();
const { showError, showSuccess } = useNotification();

const loading = ref(true);
const saving = ref(false);
const creating = ref(false);
const loadingPerfiles = ref(false);
const savingPerfil = ref(false);
const showCreateModal = ref(false);
const showPerfilModal = ref(false);
const perfilEditando = ref<PerfilCargaMasiva | null>(null);
const perfilAEliminar = ref<PerfilCargaMasiva | null>(null);
const extractingConstancia = ref(false);
const constanciaInput = ref<HTMLInputElement | null>(null);
const extractionWarnings = ref<string[]>([]);
const activeTab = ref<"datos" | "carga-masiva">("datos");
const perfilesCargaMasiva = ref<PerfilCargaMasiva[]>([]);
const formatosImportacion = ref<FormatoImportacion[]>([]);
const puntosVenta = ref<PuntoVenta[]>([]);

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
  { value: "ultimo_dia_mes_anterior", label: "Último día del mes anterior" },
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

const crearFormularioVacio = () => ({
  razon_social: "",
  cuit: "",
  condicion_iva: "RI",
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
const formatosOptions = computed(() => [
  { value: "", label: "Sin formato preseleccionado" },
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

const crearPayload = (source: typeof form): EmpresaCreate => ({
  razon_social: source.razon_social.trim(),
  cuit: source.cuit.replace(/\D/g, ""),
  condicion_iva: source.condicion_iva as Empresa["condicion_iva"],
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
    const [perfiles, formatos, puntos] = await Promise.all([
      perfilesCargaMasivaService.listar(),
      formatosImportacionService.listar(),
      puntosVentaService.getAll(),
    ]);
    perfilesCargaMasiva.value = perfiles;
    formatosImportacion.value = formatos;
    puntosVenta.value = puntos;
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
        <h1 class="text-3xl font-bold text-gray-900">Emisores</h1>
        <p class="mt-2 max-w-3xl text-gray-600">
          Administra los datos fiscales de las personas o razones sociales que
          emiten comprobantes.
        </p>
      </div>

      <div class="flex flex-wrap gap-3">
        <BaseButton variant="secondary" class="gap-2" @click="abrirCrearEmisor">
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
      <nav class="-mb-px flex gap-6" aria-label="Secciones de emisor">
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

    <div v-if="loading" class="flex justify-center py-16">
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
            <BaseInput v-model="form.localidad" label="Localidad" required />
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
            <BaseInput v-model="form.telefono" label="Teléfono" type="tel" />
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
                  <p class="text-sm text-gray-500">Emisor activo</p>
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
                  <p class="text-sm text-gray-500">CUIT</p>
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
                  <p class="text-sm text-gray-500">Última actualización</p>
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
                Si el emisor es una persona fisica, usa su nombre fiscal tal
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

      <div v-else class="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <BaseCard title="Perfiles de carga masiva">
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p class="text-sm text-gray-600">
              Configura valores habituales para precargar Emisión masiva. El
              usuario siempre podrá revisar y editar todo antes de validar.
            </p>
            <BaseButton class="gap-2" @click="abrirCrearPerfil">
              <PlusIcon class="h-5 w-5" />
              Nuevo perfil
            </BaseButton>
          </div>

          <div v-if="loadingPerfiles" class="flex justify-center py-10">
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
                  <p class="font-semibold text-gray-900">{{ perfil.nombre }}</p>
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

          <BaseAlert v-else type="info" class="mt-5">
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
    </template>

    <BaseAlert v-else type="warning">
      No hay un emisor seleccionado. Agrega un emisor para empezar a configurar
      certificados, puntos de venta y comprobantes.
    </BaseAlert>

    <BaseModal
      :show="showCreateModal"
      title="Agregar emisor"
      size="xl"
      @close="cerrarCrearEmisor"
    >
      <form class="space-y-5" @submit.prevent="crearEmisor">
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
          />
        </div>

        <BaseAlert v-if="extractionWarnings.length > 0" type="warning">
          <p class="mb-2 font-medium">Revisa estos datos manualmente:</p>
          <ul class="list-disc space-y-1 pl-5">
            <li v-for="warning in extractionWarnings" :key="warning">
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
          <BaseButton type="submit" :loading="creating">
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
      <form class="space-y-5" @submit.prevent="guardarPerfil">
        <BaseAlert type="info">
          El perfil solo precarga la pantalla de Emisión masiva. Las fechas,
          punto de venta, concepto fiscal ARCA y descripción facturada quedan
          visibles y editables antes de validar.
        </BaseAlert>

        <div class="grid gap-4 md:grid-cols-2">
          <BaseInput v-model="perfilForm.nombre" label="Nombre" required />
          <BaseSelect
            v-model="perfilFormatoImportacionVersionId"
            :options="formatosOptions"
            label="Formato de importación opcional"
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
          />
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
          <BaseButton type="submit" :loading="savingPerfil">
            Guardar perfil
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
  </div>
</template>
