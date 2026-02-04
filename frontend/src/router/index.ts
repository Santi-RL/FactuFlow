import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Layouts
import AppLayout from '@/components/layout/AppLayout.vue'

// Views
import LoginView from '@/views/auth/LoginView.vue'
import SetupView from '@/views/auth/SetupView.vue'
import DashboardView from '@/views/dashboard/DashboardView.vue'
import ClientesListView from '@/views/clientes/ClientesListView.vue'
import ClienteFormView from '@/views/clientes/ClienteFormView.vue'
import ClienteDetailView from '@/views/clientes/ClienteDetailView.vue'
import EmpresaConfigView from '@/views/empresa/EmpresaConfigView.vue'
import ComprobantesListView from '@/views/comprobantes/ComprobantesListView.vue'
import ComprobanteNuevoView from '@/views/comprobantes/ComprobanteNuevoView.vue'
import ComprobanteDetalleView from '@/views/comprobantes/ComprobanteDetalleView.vue'
import CertificadosListView from '@/views/certificados/CertificadosListView.vue'
import CertificadoWizardView from '@/views/certificados/CertificadoWizardView.vue'
import CertificadoExitoView from '@/views/certificados/CertificadoExitoView.vue'
import ReportesView from '@/views/reportes/ReportesView.vue'
import ReporteVentasView from '@/views/reportes/ReporteVentasView.vue'
import ReporteIvaView from '@/views/reportes/ReporteIvaView.vue'
import RankingClientesView from '@/views/reportes/RankingClientesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { guest: true }
    },
    {
      path: '/setup',
      name: 'setup',
      component: SetupView,
      meta: { guest: true }
    },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardView
        },
        {
          path: 'clientes',
          name: 'clientes',
          component: ClientesListView
        },
        {
          path: 'clientes/nuevo',
          name: 'cliente-nuevo',
          component: ClienteFormView
        },
        {
          path: 'clientes/:id',
          name: 'cliente-detalle',
          component: ClienteDetailView
        },
        {
          path: 'clientes/:id/editar',
          name: 'cliente-editar',
          component: ClienteFormView
        },
        {
          path: 'empresa',
          name: 'empresa',
          component: EmpresaConfigView
        },
        {
          path: 'comprobantes',
          name: 'comprobantes',
          component: ComprobantesListView
        },
        {
          path: 'comprobantes/nuevo',
          name: 'comprobante-nuevo',
          component: ComprobanteNuevoView
        },
        {
          path: 'comprobantes/:id',
          name: 'comprobante-detalle',
          component: ComprobanteDetalleView
        },
        {
          path: 'certificados',
          name: 'certificados',
          component: CertificadosListView
        },
        {
          path: 'certificados/nuevo',
          name: 'certificado-wizard',
          component: CertificadoWizardView
        },
        {
          path: 'certificados/:id/renovar',
          name: 'certificado-renovar',
          component: CertificadoWizardView,
          props: { renovar: true }
        },
        {
          path: 'certificados/:id/exito',
          name: 'certificado-exito',
          component: CertificadoExitoView
        },
        {
          path: 'reportes',
          name: 'reportes',
          component: ReportesView
        },
        {
          path: 'reportes/ventas',
          name: 'reporte-ventas',
          component: ReporteVentasView
        },
        {
          path: 'reportes/iva',
          name: 'reporte-iva',
          component: ReporteIvaView
        },
        {
          path: 'reportes/clientes',
          name: 'reporte-clientes',
          component: RankingClientesView
        }
      ]
    }
  ]
})

// Navigation guards
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Inicializar auth si no está inicializado
  if (!authStore.isAuthenticated && localStorage.getItem('token')) {
    authStore.init()
  }

  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  const guestOnly = to.matched.some(record => record.meta.guest)

  if (requiresAuth && !authStore.isAuthenticated) {
    // Redirigir a login si la ruta requiere autenticación
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (guestOnly && authStore.isAuthenticated) {
    // Redirigir a dashboard si ya está autenticado y va a login/setup
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
