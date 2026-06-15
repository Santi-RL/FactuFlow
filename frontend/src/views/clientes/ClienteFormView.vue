<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useClientesStore } from "@/stores/clientes";
import { useNotification } from "@/composables/useNotification";
import { provinciasOptions } from "@/constants/provincias";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import type { ClienteCreate, ClienteUpdate } from "@/types/cliente";

const route = useRoute();
const router = useRouter();
const clientesStore = useClientesStore();
const { showSuccess, showError } = useNotification();

const loading = ref(false);
const isEdit = ref(false);
const clienteId = ref<number | null>(null);

const formData = ref<ClienteCreate | ClienteUpdate>({
  razon_social: "",
  tipo_documento: "CUIT",
  numero_documento: "",
  condicion_iva: "RI",
  domicilio: "",
  localidad: "",
  provincia: "",
  codigo_postal: "",
  email: "",
  telefono: "",
  notas: "",
});

const tipoDocumentoOptions = [
  { value: "CUIT", label: "CUIT" },
  { value: "CUIL", label: "CUIL" },
  { value: "DNI", label: "DNI" },
  { value: "LE", label: "LE" },
  { value: "LC", label: "LC" },
  { value: "Pasaporte", label: "Pasaporte" },
  { value: "CI", label: "CI" },
];

const condicionIvaOptions = [
  { value: "RI", label: "Responsable Inscripto" },
  { value: "Monotributo", label: "Monotributo" },
  { value: "CF", label: "Consumidor Final" },
  { value: "Exento", label: "Exento" },
];

onMounted(async () => {
  const id = route.params.id;
  if (id && id !== "nuevo") {
    isEdit.value = true;
    clienteId.value = parseInt(id as string);

    loading.value = true;
    try {
      await clientesStore.fetchCliente(clienteId.value);
      if (clientesStore.clienteActual) {
        const cliente = clientesStore.clienteActual;
        formData.value = {
          razon_social: cliente.razon_social,
          tipo_documento: cliente.tipo_documento,
          numero_documento: cliente.numero_documento,
          condicion_iva: cliente.condicion_iva,
          domicilio: cliente.domicilio ?? "",
          localidad: cliente.localidad ?? "",
          provincia: cliente.provincia ?? "",
          codigo_postal: cliente.codigo_postal ?? "",
          email: cliente.email ?? "",
          telefono: cliente.telefono ?? "",
          notas: cliente.notas ?? "",
        };
      }
    } catch (error) {
      showError("Error", "No se pudo cargar el cliente");
      router.push("/clientes");
    } finally {
      loading.value = false;
    }
  }
});

const handleSubmit = async () => {
  loading.value = true;
  try {
    if (isEdit.value && clienteId.value) {
      await clientesStore.updateCliente(clienteId.value, formData.value);
      showSuccess(
        "Cliente actualizado",
        "Los cambios se guardaron correctamente",
      );
    } else {
      await clientesStore.createCliente(formData.value as ClienteCreate);
      showSuccess("Cliente creado", "El cliente se creó correctamente");
    }
    router.push("/clientes");
  } catch (error: any) {
    const detail = error.response?.data?.detail;
    showError(
      "Error",
      detail || error.message || "No se pudo guardar el cliente",
    );
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  router.push("/clientes");
};
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-brand-ink">
        {{ isEdit ? "Editar Cliente" : "Nuevo Cliente" }}
      </h1>
      <p class="mt-2 text-brand-slate">
        {{
          isEdit
            ? "Actualizar información del cliente"
            : "Agregar un nuevo cliente"
        }}
      </p>
    </div>

    <BaseCard>
      <form
        class="space-y-6"
        @submit.prevent="handleSubmit"
      >
        <div>
          <h3 class="mb-4 text-lg font-semibold text-brand-ink">
            Información Básica
          </h3>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <BaseInput
                v-model="formData.razon_social"
                label="Razón Social"
                placeholder="Nombre o razón social del cliente"
                required
              />
            </div>

            <BaseSelect
              v-model="formData.tipo_documento"
              label="Tipo de Documento"
              :options="tipoDocumentoOptions"
              required
            />

            <BaseInput
              v-model="formData.numero_documento"
              label="Número de Documento"
              placeholder="20123456789"
              required
            />

            <BaseSelect
              v-model="formData.condicion_iva"
              label="Condición IVA"
              :options="condicionIvaOptions"
              required
            />
          </div>
        </div>

        <div>
          <h3 class="mb-4 text-lg font-semibold text-brand-ink">
            Domicilio
          </h3>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <BaseInput
                v-model="formData.domicilio"
                label="Domicilio"
                placeholder="Calle y número"
              />
            </div>

            <BaseInput
              v-model="formData.localidad"
              label="Localidad"
              placeholder="Ciudad"
            />

            <BaseSelect
              v-model="formData.provincia"
              label="Provincia"
              :options="provinciasOptions"
            />

            <BaseInput
              v-model="formData.codigo_postal"
              label="Código Postal"
              placeholder="1234"
            />
          </div>
        </div>

        <div>
          <h3 class="mb-4 text-lg font-semibold text-brand-ink">
            Contacto
          </h3>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <BaseInput
              v-model="formData.email"
              type="email"
              label="Email"
              placeholder="cliente@ejemplo.com"
            />

            <BaseInput
              v-model="formData.telefono"
              type="tel"
              label="Teléfono"
              placeholder="011-1234-5678"
            />

            <div class="md:col-span-2">
              <label class="mb-1 block text-sm font-medium text-brand-ink">
                Notas
              </label>
              <textarea
                v-model="formData.notas"
                rows="3"
                class="w-full rounded-control border border-border-subtle bg-surface-card px-3 py-2 text-brand-ink placeholder:text-brand-slate transition-colors focus:outline-none focus:ring-2 focus:ring-brand-flow"
                placeholder="Información adicional sobre el cliente"
              />
            </div>
          </div>
        </div>

        <div
          class="flex flex-col-reverse gap-3 border-t border-border-subtle pt-4 sm:flex-row sm:justify-end"
        >
          <BaseButton
            class="w-full sm:w-auto"
            type="button"
            variant="secondary"
            :disabled="loading"
            @click="handleCancel"
          >
            Cancelar
          </BaseButton>
          <BaseButton
            class="w-full sm:w-auto"
            type="submit"
            :loading="loading"
          >
            {{ isEdit ? "Guardar Cambios" : "Crear Cliente" }}
          </BaseButton>
        </div>
      </form>
    </BaseCard>
  </div>
</template>
