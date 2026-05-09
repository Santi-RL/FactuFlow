<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import { useNotification } from "@/composables/useNotification";
import { useEmpresaStore } from "@/stores/empresa";
import type { Empresa, EmpresaCreate, EmpresaUpdate } from "@/types/empresa";
import {
  BuildingOffice2Icon,
  CalendarDaysIcon,
  DocumentArrowUpIcon,
  IdentificationIcon,
  PlusIcon,
} from "@heroicons/vue/24/outline";
import { empresaService } from "@/services/empresa.service";

const empresaStore = useEmpresaStore();
const { showError, showSuccess } = useNotification();

const loading = ref(true);
const saving = ref(false);
const creating = ref(false);
const showCreateModal = ref(false);
const extractingConstancia = ref(false);
const constanciaInput = ref<HTMLInputElement | null>(null);
const extractionWarnings = ref<string[]>([]);

const empresaActiva = computed(() => empresaStore.empresaActiva);
const condicionIvaOptions = [
  { value: "RI", label: "Responsable Inscripto" },
  { value: "Monotributo", label: "Monotributo" },
  { value: "Exento", label: "Exento" },
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

const sincronizarFormulario = (empresa: Empresa | null) => {
  if (!empresa) return;

  form.razon_social = empresa.razon_social;
  form.cuit = empresa.cuit;
  form.condicion_iva = empresa.condicion_iva;
  form.domicilio = empresa.domicilio;
  form.localidad = empresa.localidad;
  form.provincia = empresa.provincia;
  form.codigo_postal = empresa.codigo_postal;
  form.email = empresa.email || "";
  form.telefono = empresa.telefono || "";
  form.inicio_actividades = empresa.inicio_actividades;
};

const resetCreateForm = () => {
  Object.assign(createForm, crearFormularioVacio());
};

const crearPayload = (source: typeof form): EmpresaCreate => ({
  razon_social: source.razon_social.trim(),
  cuit: source.cuit.replace(/\D/g, ""),
  condicion_iva: source.condicion_iva as Empresa["condicion_iva"],
  domicilio: source.domicilio.trim(),
  localidad: source.localidad.trim(),
  provincia: source.provincia.trim(),
  codigo_postal: source.codigo_postal.trim(),
  email: source.email.trim() || undefined,
  telefono: source.telefono.trim() || undefined,
  inicio_actividades: source.inicio_actividades,
});

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
    aplicarValorExtraido("provincia", datos.provincia);
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
});

onMounted(async () => {
  await cargarEmpresa();
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

    <div v-if="loading" class="flex justify-center py-16">
      <BaseSpinner size="lg" />
    </div>

    <template v-else-if="empresaActiva">
      <div class="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
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
            <BaseInput v-model="form.provincia" label="Provincia" required />
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
          <BaseInput
            v-model="createForm.provincia"
            label="Provincia"
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
  </div>
</template>
