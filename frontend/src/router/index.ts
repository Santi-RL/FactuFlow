import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Layout principal - carga inmediata
import AppLayout from '@/components/layout/AppLayout.vue'

// Views públicas - carga inmediata para mejor UX
import LoginView from '@/views/auth/LoginView.vue'
import SetupView from '@/views/auth/SetupView.vue'

// Dashboard - carga inmediata (primera vista del usuario)
import DashboardView from '@/views/dashboard/DashboardView.vue'

// Vistas protegidas - lazy loading para optimización
const ClientesListView = () => import('@/views/clientes/ClientesListView.vue')
const ClienteFormView = () => import('@/views/clientes/ClienteFormView.vue')
const ClienteDetailView = () => import('@/views/clientes/ClienteDetailView.vue')
const EmpresaConfigView = () => import('@/views/empresa/EmpresaConfigView.vue')
const ComprobantesListView = () => import('@/views/comprobantes/ComprobantesListView.vue')
const ComprobanteNuevoView = () => import('@/views/comprobantes/ComprobanteNuevoView.vue')
const ComprobanteDetalleView = () => import('@/views/comprobantes/ComprobanteDetalleView.vue')
const CertificadosListView = () => import('@/views/certificados/CertificadosListView.vue')
const CertificadoWizardView = () => import('@/views/certificados/CertificadoWizardView.vue')
const CertificadoExitoView = () => import('@/views/certificados/CertificadoExitoView.vue')
const ReportesView = () => import('@/views/reportes/ReportesView.vue')
const ReporteVentasView = () => import('@/views/reportes/ReporteVentasView.vue')
const ReporteIvaView = () => import('@/views/reportes/ReporteIvaView.vue')
const RankingClientesView = () => import('@/views/reportes/RankingClientesView.vue')

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
