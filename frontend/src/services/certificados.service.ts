import apiClient from './api'
import type {
  Certificado,
  GenerarCSRRequest,
  GenerarCSRResponse,
  VerificacionResponse,
  CertificadoAlerta
} from '@/types/certificado'

/**
 * Servicio para gestión de certificados ARCA
 */
class CertificadosService {
  private readonly basePath = '/api/certificados'

  /**
   * Obtiene todos los certificados
   */
  async listar(): Promise<Certificado[]> {
    const response = await apiClient.get(this.basePath)
    return response.data
  }

  /**
   * Obtiene un certificado por ID
   */
  async obtener(id: number): Promise<Certificado> {
    const response = await apiClient.get(`${this.basePath}/${id}`)
    return response.data
  }

  /**
   * Elimina un certificado
   */
  async eliminar(id: number): Promise<void> {
    await apiClient.delete(`${this.basePath}/${id}`)
  }

  /**
   * Genera clave privada y CSR
   */
  async generarCSR(data: GenerarCSRRequest): Promise<GenerarCSRResponse> {
    const response = await apiClient.post(`${this.basePath}/generar-csr`, data)
    return response.data
  }

  /**
   * Sube un certificado desde el portal de ARCA
   */
  async subirCertificado(
    file: File,
    cuit: string,
    nombre: string,
    ambiente: string,
    keyFilename: string
  ): Promise<Certificado> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('cuit', cuit)
    formData.append('nombre', nombre)
    formData.append('ambiente', ambiente)
    formData.append('key_filename', keyFilename)

    const response = await apiClient.post(
      `${this.basePath}/subir-certificado`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    )
    return response.data
  }

  /**
   * Verifica la conexión con ARCA usando un certificado
   */
  async verificarConexion(certificadoId: number): Promise<VerificacionResponse> {
    const response = await apiClient.post(
      `${this.basePath}/verificar-conexion/${certificadoId}`
    )
    return response.data
  }

  /**
   * Obtiene alertas de certificados próximos a vencer
   */
  async obtenerAlertasVencimiento(): Promise<CertificadoAlerta[]> {
    const response = await apiClient.get(`${this.basePath}/alertas-vencimiento`)
    return response.data
  }

  /**
   * Lista claves privadas disponibles para un CUIT y ambiente
   */
  async listarClaves(cuit: string, ambiente: string): Promise<string[]> {
    const response = await apiClient.get(`${this.basePath}/keys`, {
      params: { cuit, ambiente }
    })
    return response.data
  }

  /**
   * Descarga el CSR como archivo
   */
  descargarCSR(csr: string, cuit: string): void {
    const blob = new Blob([csr], { type: 'application/pkcs10' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${cuit}_solicitud.csr`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }
}

export default new CertificadosService()
