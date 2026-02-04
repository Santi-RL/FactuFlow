/**
 * Servicio para gestión de PDFs
 */

import api from './api'

export interface PDFDownloadOptions {
  comprobanteId: number
  preview?: boolean
}

class PDFService {
  /**
   * Descarga el PDF de un comprobante
   */
  async descargarPDF(comprobanteId: number): Promise<Blob> {
    const response = await api.get(`/pdf/comprobante/${comprobanteId}`, {
      responseType: 'blob'
    })
    return response.data
  }

  /**
   * Abre el PDF de un comprobante en una nueva ventana
   */
  async previsualizarPDF(comprobanteId: number): Promise<void> {
    const response = await api.get(`/pdf/comprobante/${comprobanteId}/preview`, {
      responseType: 'blob'
    })
    
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    window.open(url, '_blank')
    
    // Liberar el objeto URL después de un tiempo
    setTimeout(() => window.URL.revokeObjectURL(url), 100)
  }

  /**
   * Descarga automáticamente el PDF
   */
  async descargarAutomatico(comprobanteId: number, filename?: string): Promise<void> {
    const blob = await this.descargarPDF(comprobanteId)
    
    // Crear un enlace temporal y hacer click
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename || `Comprobante_${comprobanteId}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    // Liberar el objeto URL
    window.URL.revokeObjectURL(url)
  }
}

export default new PDFService()
