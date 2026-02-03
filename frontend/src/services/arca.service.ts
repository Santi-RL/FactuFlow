import apiClient from './api'

export const arcaService = {
  async getStatus(): Promise<any> {
    const response = await apiClient.get('/api/arca/status')
    return response.data
  },

  async testConnection(): Promise<any> {
    const response = await apiClient.post('/api/arca/test')
    return response.data
  }
}
