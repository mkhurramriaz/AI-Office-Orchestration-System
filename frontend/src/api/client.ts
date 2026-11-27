import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { TokenResponse } from '../types/api'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
export const api = axios.create({ baseURL: apiBaseUrl.replace(/\/$/, ''), headers: { 'Content-Type': 'application/json' } })

const ACCESS_KEY = 'taskflow.access_token'
const REFRESH_KEY = 'taskflow.refresh_token'
export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  save: (tokens: TokenResponse) => {
    localStorage.setItem(ACCESS_KEY, tokens.access_token)
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshInFlight: Promise<string | null> | null = null
api.interceptors.response.use(
  response => response,
  async (error: AxiosError<{ error?: { message?: string }; detail?: string }>) => {
    const request = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isCredentialRequest = /\/auth\/(login|register|refresh)$/.test(request?.url ?? '')
    if (error.response?.status === 401 && request && !request._retried && !isCredentialRequest) {
      const refreshToken = tokenStore.getRefresh()
      if (refreshToken) {
        request._retried = true
        refreshInFlight ??= axios.post<TokenResponse>(`${api.defaults.baseURL}/auth/refresh`, { refresh_token: refreshToken })
          .then(({ data }) => { tokenStore.save(data); return data.access_token })
          .catch(() => { tokenStore.clear(); return null })
          .finally(() => { refreshInFlight = null })
        const accessToken = await refreshInFlight
        if (accessToken) {
          request.headers.Authorization = `Bearer ${accessToken}`
          return api(request)
        }
      }
      tokenStore.clear()
      window.dispatchEvent(new Event('taskflow:unauthorized'))
    }
    return Promise.reject(error)
  },
)

export function getApiError(error: unknown, fallback = 'Something went wrong. Please try again.') {
  if (axios.isAxiosError<{ error?: { message?: string }; detail?: string }>(error)) {
    return error.response?.data?.error?.message || error.response?.data?.detail || error.message || fallback
  }
  return error instanceof Error ? error.message : fallback
}
