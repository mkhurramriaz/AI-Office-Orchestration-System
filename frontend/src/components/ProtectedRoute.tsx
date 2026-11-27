import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import type { UserRole } from '../types/api'
import { LoadingScreen } from './LoadingScreen'
import { UnauthorizedPage } from '../pages/UnauthorizedPage'

export function ProtectedRoute({ allowedRoles }: { allowedRoles?: UserRole[] }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <LoadingScreen />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (allowedRoles && !allowedRoles.includes(user.role)) return <UnauthorizedPage />
  return <Outlet />
}
