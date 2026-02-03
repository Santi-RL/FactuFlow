export interface ApiError {
  detail: string | Record<string, any>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ListParams {
  page?: number
  per_page?: number
  search?: string
}
