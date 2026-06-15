<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useClientesStore } from "@/stores/clientes";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseBadge from "@/components/ui/BaseBadge.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import { PencilIcon, ArrowLeftIcon } from "@heroicons/vue/24/outline";

const route = useRoute();
const router = useRouter();
const clientesStore = useClientesStore();

const loading = ref(true);

onMounted(async () => {
  const id = parseInt(route.params.id as string);
  try {
    await clientesStore.fetchCliente(id);
  } catch (error) {
    router.push("/clientes");
  } finally {
    loading.value = false;
  }
});

const handleEdit = () => {
  router.push(`/clientes/${route.params.id}/editar`);
};

const handleBack = () => {
  router.push("/clientes");
};
</script>

<template>
  <div>
    <div class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-3xl font-bold text-brand-ink">
          Detalle del Cliente
        </h1>
      </div>
      <div class="flex flex-col gap-3 sm:flex-row">
        <BaseButton
          class="w-full sm:w-auto"
          variant="secondary"
          @click="handleBack"
        >
          <ArrowLeftIcon class="h-5 w-5 mr-2" />
          Volver
        </BaseButton>
        <BaseButton
          class="w-full sm:w-auto"
          @click="handleEdit"
        >
          <PencilIcon class="h-5 w-5 mr-2" />
          Editar
        </BaseButton>
      </div>
    </div>

    <BaseSpinner v-if="loading" />

    <BaseCard v-else-if="clientesStore.clienteActual">
      <div class="space-y-6">
        <div>
          <h3 class="mb-4 text-lg font-semibold text-brand-ink">
            Información Básica
          </h3>
          <dl class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Razón Social
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.razon_social }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Documento
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.tipo_documento }}:
                {{ clientesStore.clienteActual.numero_documento }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Condición IVA
              </dt>
              <dd class="mt-1">
                <BaseBadge>
                  {{
                    clientesStore.clienteActual.condicion_iva
                  }}
                </BaseBadge>
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Estado
              </dt>
              <dd class="mt-1">
                <BaseBadge
                  :variant="
                    clientesStore.clienteActual.activo ? 'success' : 'default'
                  "
                >
                  {{
                    clientesStore.clienteActual.activo ? "Activo" : "Inactivo"
                  }}
                </BaseBadge>
              </dd>
            </div>
          </dl>
        </div>

        <div
          v-if="clientesStore.clienteActual.domicilio"
          class="border-t border-border-subtle pt-6"
        >
          <h3 class="mb-4 text-lg font-semibold text-brand-ink">
            Domicilio
          </h3>
          <dl class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Dirección
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.domicilio || "-" }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Localidad
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.localidad || "-" }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Provincia
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.provincia || "-" }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Código Postal
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.codigo_postal || "-" }}
              </dd>
            </div>
          </dl>
        </div>

        <div class="border-t border-border-subtle pt-6">
          <h3 class="mb-4 text-lg font-semibold text-brand-ink">
            Contacto
          </h3>
          <dl class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Email
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.email || "-" }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-brand-slate">
                Teléfono
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.telefono || "-" }}
              </dd>
            </div>
            <div
              v-if="clientesStore.clienteActual.notas"
              class="md:col-span-2"
            >
              <dt class="text-sm font-medium text-brand-slate">
                Notas
              </dt>
              <dd class="mt-1 text-sm text-brand-ink">
                {{ clientesStore.clienteActual.notas }}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </BaseCard>
  </div>
</template>
