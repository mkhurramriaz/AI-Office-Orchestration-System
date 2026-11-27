import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthProvider'
import { authApi } from '../api/auth'
import { adminApi } from '../api/admin'
import { workspaceApi } from '../api/workspace'
import type { AdminOverview, Notification, User } from '../types/api'
import App from '../App'

vi.mock('../api/auth', () => ({ authApi: { me: vi.fn(), login: vi.fn(), register: vi.fn() } }))
vi.mock('../api/admin', () => ({ adminApi: { overview: vi.fn(), users: vi.fn(), createUser: vi.fn(), updateUser: vi.fn(), notifications: vi.fn() } }))
vi.mock('../api/workspace', () => ({ workspaceApi: { projects: vi.fn(), project: vi.fn(), tasks: vi.fn(), task: vi.fn(), updateTaskStatus: vi.fn(), chat: vi.fn(), startWorkflow: vi.fn(), workflow: vi.fn(), decideWorkflow: vi.fn() }, getTrackedWorkflowIds: vi.fn(() => []), trackWorkflow: vi.fn() }))

const date = '2026-11-27T10:00:00Z'
const admin: User = { id: 'admin-1', email: 'admin@example.com', full_name: 'Ada Admin', role: 'ADMIN', department: 'OPERATIONS', job_title: 'Administrator', professional_role: null, is_active: true, created_at: date, updated_at: date }
const employee: User = { ...admin, id: 'employee-1', email: 'employee@example.com', full_name: 'Evan Employee', role: 'EMPLOYEE', department: 'AI', professional_role: 'AI_ENGINEER', job_title: 'AI Engineer' }
const overview: AdminOverview = { total_users: 2, active_users: 2, inactive_users: 0, users_by_account_role: { ADMIN: 1, MANAGER: 0, EMPLOYEE: 1 }, employees_by_department: { AI: 1 }, employees_by_professional_role: { AI_ENGINEER: 1 }, total_projects: 1, projects_by_status: { ACTIVE: 1 }, total_tasks: 2, tasks_by_status: { TODO: 1, IN_PROGRESS: 1 } }
const notification: Notification = { id: 'notice-1', recipient_id: admin.id, title: 'Task updated', message: 'A task status changed.', notification_type: 'STATUS_CHANGED', is_read: false, created_at: date }
const page = { items: [employee], total: 1, page: 1, size: 10, pages: 1 }

function renderAt(path: string, profile: User = admin) {
  localStorage.setItem('taskflow.access_token', 'test-access')
  localStorage.setItem('taskflow.refresh_token', 'test-refresh')
  vi.mocked(authApi.me).mockResolvedValue(profile)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter></QueryClientProvider>)
}

describe('admin dashboard', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('confirm', vi.fn(() => true))
    vi.mocked(adminApi.overview).mockResolvedValue(overview)
    vi.mocked(adminApi.users).mockResolvedValue(page)
    vi.mocked(adminApi.notifications).mockResolvedValue({ items: [notification], total: 1, page: 1, size: 100, pages: 1 })
    vi.mocked(adminApi.createUser).mockResolvedValue(employee)
    vi.mocked(adminApi.updateUser).mockImplementation(async (_id, payload) => ({ ...employee, ...payload }))
    vi.mocked(workspaceApi.projects).mockResolvedValue({ items: [], total: 1, page: 1, size: 100, pages: 1 })
  })
  afterEach(() => cleanup())

  it('routes administrators to organization overview with live statistics', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { name: 'Organization overview' })).toBeInTheDocument()
    expect(await screen.findByText('2 active · 0 inactive')).toBeInTheDocument()
    expect(screen.getByText('AI Engineer')).toBeInTheDocument()
    expect(screen.getByText('Task updated')).toBeInTheDocument()
  })

  it('blocks non-admins from admin pages', async () => {
    renderAt('/admin/employees', { ...employee, role: 'EMPLOYEE' })
    expect(await screen.findByRole('heading', { name: 'Access unavailable' })).toBeInTheDocument()
  })

  it('searches and filters users through paginated backend parameters', async () => {
    const user = userEvent.setup()
    renderAt('/admin/employees')
    await screen.findByText('employee@example.com')
    await user.type(screen.getByPlaceholderText('Search accounts…'), 'Evan')
    await user.selectOptions(screen.getByLabelText('Department'), 'AI')
    await user.selectOptions(screen.getByLabelText('Professional role'), 'AI_ENGINEER')
    await user.selectOptions(screen.getByLabelText('Account status'), 'true')
    await waitFor(() => expect(adminApi.users).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'Evan', department: 'AI', professional_role: 'AI_ENGINEER', is_active: true, page: 1, size: 10 })))
  })

  it('moves through user result pages', async () => {
    const user = userEvent.setup()
    vi.mocked(adminApi.users).mockResolvedValue({ ...page, pages: 2 })
    renderAt('/admin/employees')
    await screen.findByText('employee@example.com')
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(adminApi.users).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, size: 10 })))
  })

  it('creates a user with separate account and professional roles', async () => {
    const user = userEvent.setup()
    renderAt('/admin/employees')
    await user.click(await screen.findByRole('button', { name: 'Create account' }))
    await user.type(screen.getByLabelText('Full name'), 'Evan Employee')
    await user.type(screen.getByLabelText('Email'), 'employee@example.com')
    await user.type(screen.getByLabelText('Temporary password'), 'Password123!')
    const dialog = within(screen.getByRole('dialog'))
    const selects = dialog.getAllByRole('combobox')
    await user.selectOptions(selects[0], 'EMPLOYEE')
    await user.selectOptions(selects[1], 'AI')
    await user.selectOptions(selects[2], 'AI_ENGINEER')
    await user.click(dialog.getByRole('button', { name: 'Create account' }))
    await waitFor(() => expect(vi.mocked(adminApi.createUser).mock.calls.at(-1)?.[0]).toEqual(expect.objectContaining({ role: 'EMPLOYEE', professional_role: 'AI_ENGINEER', department: 'AI' })))
  })

  it('edits professional role and activation status', async () => {
    const user = userEvent.setup()
    renderAt('/admin/employees')
    await user.click(await screen.findByRole('button', { name: 'Edit' }))
    const dialog = within(screen.getByRole('dialog'))
    await user.selectOptions(dialog.getAllByRole('combobox')[0], 'MANAGER')
    await user.selectOptions(dialog.getAllByRole('combobox')[2], 'QA_ENGINEER')
    await user.click(dialog.getByRole('checkbox'))
    await user.click(dialog.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(adminApi.updateUser).toHaveBeenCalledWith('employee-1', expect.objectContaining({ role: 'MANAGER', professional_role: 'QA_ENGINEER', is_active: false })))
  })

  it('shows department counts and makes department catalog read-only', async () => {
    renderAt('/admin/departments')
    expect(await screen.findByRole('heading', { name: 'Departments' })).toBeInTheDocument()
    expect(screen.getByText('Department catalog is not editable')).toBeInTheDocument()
    expect(await screen.findByText('1 employee')).toBeInTheDocument()
  })

  it('shows notification empty states and API failures', async () => {
    vi.mocked(adminApi.notifications).mockResolvedValue({ items: [], total: 0, page: 1, size: 100, pages: 1 })
    renderAt('/admin/notifications')
    expect(await screen.findByText('No notifications')).toBeInTheDocument()
    cleanup()
    vi.mocked(adminApi.overview).mockRejectedValue(new Error('Service unavailable'))
    renderAt('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable')
  })
})
