import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '../api/auth'
import { getApiError, tokenStore } from '../api/client'
import type { LoginRequest, RegisterRequest, User } from '../types/api'

interface AuthContextValue {
  user: User | null
  loading: boolean
  error: string | null
  login: (payload: LoginRequest) => Promise<void>
  register: (payload: RegisterRequest) => Promise<void>
  logout: () => void
  clearError: () => void
}
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const hasToken = Boolean(tokenStore.getAccess())
  const profile = useQuery({ queryKey: ['auth', 'me'], queryFn: authApi.me, enabled: hasToken, retry: false })
  const user = profile.data ?? null

  const logout = useCallback(() => {
    tokenStore.clear()
    queryClient.setQueryData(['auth', 'me'], null)
    void queryClient.invalidateQueries({ queryKey: ['auth'] })
    window.location.assign('/login')
  }, [queryClient])

  useEffect(() => {
    const listener = () => logout()
    window.addEventListener('taskflow:unauthorized', listener)
    return () => window.removeEventListener('taskflow:unauthorized', listener)
  }, [logout])

  const login = async (payload: LoginRequest) => {
    setError(null)
    try {
      const tokens = await authApi.login(payload)
      tokenStore.save(tokens)
      const currentUser = await authApi.me()
      queryClient.setQueryData(['auth', 'me'], currentUser)
    } catch (cause) {
      tokenStore.clear()
      const message = getApiError(cause, 'Unable to sign in.')
      setError(message)
      throw new Error(message)
    }
  }

  const register = async (payload: RegisterRequest) => {
    setError(null)
    try {
      await authApi.register(payload)
      await login({ email: payload.email, password: payload.password })
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : getApiError(cause, 'Unable to create your account.')
      setError(message)
      throw new Error(message)
    }
  }

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading: hasToken && profile.isPending,
    error,
    login,
    register,
    logout,
    clearError: () => setError(null),
  }), [user, hasToken, profile.isPending, error, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
