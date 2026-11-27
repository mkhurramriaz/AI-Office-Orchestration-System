import { api } from './client'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '../types/api'

export const authApi = {
  login: async (payload: LoginRequest) => (await api.post<TokenResponse>('/auth/login', payload)).data,
  register: async (payload: RegisterRequest) => (await api.post<User>('/auth/register', payload)).data,
  me: async () => (await api.get<User>('/auth/me')).data,
}
