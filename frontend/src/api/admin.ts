import { api } from './client'
import type { AdminOverview, Department, Notification, PaginatedResponse, ProfessionalRole, User, UserRole } from '../types/api'

export interface UserPageFilters {
  page: number
  size: number
  search?: string
  role?: UserRole
  department?: Department
  professional_role?: ProfessionalRole
  is_active?: boolean
}

export interface CreateUserPayload {
  full_name: string
  email: string
  password: string
  role: UserRole
  department: Department
  professional_role?: ProfessionalRole
  job_title?: string
  is_active: boolean
}

export type UpdateUserPayload = Partial<Omit<CreateUserPayload, 'password' | 'professional_role' | 'job_title'>> & {
  professional_role?: ProfessionalRole | null
  job_title?: string | null
}

export const adminApi = {
  overview: async () => (await api.get<AdminOverview>('/admin/overview')).data,
  users: async (params: UserPageFilters) => (await api.get<PaginatedResponse<User>>('/users', { params })).data,
  createUser: async (payload: CreateUserPayload) => (await api.post<User>('/users', payload)).data,
  updateUser: async (id: string, payload: UpdateUserPayload) => (await api.patch<User>(`/users/${id}`, payload)).data,
  notifications: async () => (await api.get<PaginatedResponse<Notification>>('/notifications', { params: { page: 1, size: 100 } })).data,
}
