import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import { UnauthorizedPage } from './pages/UnauthorizedPage'
import { ManagerDashboard } from './pages/ManagerDashboard'
import { NewAiProjectPage, WorkflowDetailPage, WorkflowListPage } from './pages/WorkflowPages'
import { ProjectDetailPage, ProjectListPage, TaskDetailPage, TaskListPage } from './pages/ProjectPages'
import { CopilotPage } from './pages/CopilotPage'
import { useAuth } from './auth/AuthProvider'
import { AdminDashboard, AdminDepartmentsPage, AdminEmployeesPage, AdminNotificationsPage } from './pages/AdminDashboard'

export default function App() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route element={<ProtectedRoute />}><Route element={<AppLayout />}>
      <Route index element={<DashboardRoute />} />
      <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
        <Route path="admin/employees" element={<AdminEmployeesPage />} />
        <Route path="admin/departments" element={<AdminDepartmentsPage />} />
        <Route path="admin/notifications" element={<AdminNotificationsPage />} />
      </Route>
      <Route path="projects" element={<ProjectListPage />} />
      <Route path="projects/:projectId" element={<ProjectDetailPage />} />
      <Route path="tasks" element={<TaskListPage />} />
      <Route path="tasks/:taskId" element={<TaskDetailPage />} />
      <Route path="copilot" element={<CopilotPage />} />
      <Route element={<ProtectedRoute allowedRoles={['ADMIN', 'MANAGER']} />}>
        <Route path="ai/new" element={<NewAiProjectPage />} />
        <Route path="approvals" element={<WorkflowListPage />} />
        <Route path="approvals/:workflowId" element={<WorkflowDetailPage />} />
        <Route path="team" element={<Placeholder title="Team" description="Manage and explore your workspace team." />} />
        <Route path="activity" element={<Placeholder title="Activity" description="Keep up with important workspace updates." />} />
      </Route>
    </Route></Route>
    <Route path="/unauthorized" element={<UnauthorizedPage />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}

function DashboardRoute() {
  const { user } = useAuth()
  return user?.role === 'ADMIN' ? <AdminDashboard /> : user?.role === 'MANAGER' ? <ManagerDashboard /> : <DashboardPage />
}

function Placeholder({ title, description }: { title: string; description: string }) {
  return <div><p className="text-xs font-medium text-muted">Workspace</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-2 text-sm text-muted">{description}</p><div className="mt-7 rounded-xl border border-line bg-white p-10 text-center shadow-card"><p className="text-sm font-medium">This page is ready for the next feature phase.</p><p className="mt-1 text-xs text-muted">Authentication and workspace access are already connected.</p></div></div>
}
