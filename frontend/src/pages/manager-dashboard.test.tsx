import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthProvider'
import { authApi } from '../api/auth'
import { getTrackedWorkflowIds, workspaceApi } from '../api/workspace'
import type { Project, Task, User, WorkflowExecution } from '../types/api'
import App from '../App'

vi.mock('../api/auth', () => ({ authApi: { me: vi.fn(), login: vi.fn(), register: vi.fn() } }))
vi.mock('../api/workspace', () => ({
  workspaceApi: {
    projects: vi.fn(), project: vi.fn(), tasks: vi.fn(), task: vi.fn(), updateTaskStatus: vi.fn(), chat: vi.fn(),
    startWorkflow: vi.fn(), workflow: vi.fn(), decideWorkflow: vi.fn(),
  },
  getTrackedWorkflowIds: vi.fn(() => []),
  trackWorkflow: vi.fn(),
}))

const now = '2026-11-26T10:00:00Z'
const manager: User = {
  id: 'manager-1', email: 'manager@example.com', full_name: 'Morgan Manager', role: 'MANAGER',
  department: 'OPERATIONS', job_title: 'Project Manager', professional_role: 'PROJECT_MANAGER',
  is_active: true, created_at: now, updated_at: now,
}
const project: Project = {
  id: 'project-1', project_name: 'Customer Portal', description: 'A secure portal.', original_brief: 'Build a customer portal',
  status: 'ACTIVE', created_by: manager.id, start_date: null, deadline: null, created_at: now, updated_at: now, task_count: 1,
}
const task: Task = {
  id: 'task-1', project_id: project.id, task_code: 'TASK-001', title: 'Design API', description: 'Design the API.', department: 'WEB',
  required_role: 'BACKEND_DEVELOPER', priority: 'HIGH', status: 'TODO', assigned_to: 'employee-1', assigned_by: manager.id,
  acceptance_criteria: 'Document the API', completion_notes: null, completed_at: null, created_at: now, updated_at: now, dependencies: [],
}
const plan = {
  project_name: 'Customer Portal', project_description: 'A secure customer portal.',
  tasks: [
    { task_id: 'T1', title: 'Design API', description: 'Design the service API.', required_role: 'BACKEND_DEVELOPER' as const, department: 'WEB' as const, priority: 'HIGH' as const, dependencies: [], acceptance_criteria: ['API documented'] },
    { task_id: 'T2', title: 'Build interface', description: 'Build the customer interface.', required_role: 'FRONTEND_DEVELOPER' as const, department: 'WEB' as const, priority: 'MEDIUM' as const, dependencies: ['T1'], acceptance_criteria: ['UI works'] },
  ],
}
const recommendations = {
  project_name: plan.project_name,
  assignments: [{ task_id: 'T1', task_title: 'Design API', employee_id: 'employee-1', employee_name: 'Alex Developer', department: 'WEB' as const, required_role: 'BACKEND_DEVELOPER' as const, current_workload: 2, projected_workload: 3, reason: 'Lowest workload.' }],
  unassigned_tasks: [{ task_id: 'T2', task_title: 'Build interface', reason: 'No matching employee.' }], is_fully_assigned: false,
}
const workflow: WorkflowExecution = {
  id: 'workflow-1', project_id: null, initiated_by: manager.id, status: 'INTERRUPTED', thread_id: 'thread-1',
  input_data: { project_brief: 'Build a customer portal' }, output_data: { plan, recommendations },
  error_message: null, started_at: now, completed_at: null, created_at: now, updated_at: now,
}

function renderAt(path: string, profile: User = manager) {
  localStorage.setItem('taskflow.access_token', 'test-access')
  localStorage.setItem('taskflow.refresh_token', 'test-refresh')
  vi.mocked(authApi.me).mockResolvedValue(profile)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter></QueryClientProvider>)
}

describe('manager dashboard flows', () => {
  afterEach(() => cleanup())

  beforeEach(() => {
    localStorage.clear()
    vi.mocked(workspaceApi.projects).mockResolvedValue({ items: [project], total: 1, page: 1, size: 100, pages: 1 })
    vi.mocked(workspaceApi.tasks).mockResolvedValue({ items: [task], total: 1, page: 1, size: 100, pages: 1 })
    vi.mocked(workspaceApi.task).mockResolvedValue(task)
    vi.mocked(workspaceApi.project).mockResolvedValue(project)
    vi.mocked(workspaceApi.workflow).mockResolvedValue(workflow)
    vi.mocked(workspaceApi.updateTaskStatus).mockResolvedValue({ ...task, status: 'IN_PROGRESS' })
  })

  it('shows manager metrics, recent projects, and approval queue', async () => {
    vi.mocked(workspaceApi.workflow).mockResolvedValue(workflow)
    vi.mocked(getTrackedWorkflowIds).mockReturnValue(['workflow-1'])
    renderAt('/')
    expect(await screen.findByRole('heading', { name: /Good to see you, Morgan/ })).toBeInTheDocument()
    expect(screen.getByText('Active tasks')).toBeInTheDocument()
    expect(await screen.findAllByText('Customer Portal')).toHaveLength(2)
    expect(await screen.findByText('Approval queue')).toBeInTheDocument()
  })

  it('starts AI planning and displays the generated plan and dependencies', async () => {
    const user = userEvent.setup()
    vi.mocked(workspaceApi.startWorkflow).mockResolvedValue(workflow)
    renderAt('/ai/new')
    await user.type(await screen.findByLabelText('Project brief'), 'Build a customer portal')
    await user.click(screen.getByRole('button', { name: /Generate plan/ }))
    expect(await screen.findByRole('heading', { name: 'Customer Portal' })).toBeInTheDocument()
    expect(screen.getByText(/← Design API/)).toBeInTheDocument()
    expect(await screen.findAllByText(/Alex Developer/)).toHaveLength(2)
    expect(await screen.findAllByText(/No matching employee/)).toHaveLength(2)
  })

  it('approves a plan once and shows the created project state', async () => {
    const user = userEvent.setup()
    vi.mocked(workspaceApi.workflow).mockResolvedValue(workflow)
    vi.mocked(workspaceApi.decideWorkflow).mockResolvedValue({ ...workflow, status: 'COMPLETED', project_id: project.id, output_data: { ...workflow.output_data, project_id: project.id, tasks: [task] } })
    renderAt('/approvals/workflow-1')
    await user.click(await screen.findByRole('button', { name: /Approve & create/ }))
    expect(await screen.findByText('Project approved and created')).toBeInTheDocument()
    expect(workspaceApi.decideWorkflow).toHaveBeenCalledTimes(1)
    expect(workspaceApi.decideWorkflow).toHaveBeenCalledWith('workflow-1', 'APPROVE')
  })

  it('rejects a plan and displays the rejected state', async () => {
    const user = userEvent.setup()
    vi.mocked(workspaceApi.workflow).mockResolvedValue(workflow)
    vi.mocked(workspaceApi.decideWorkflow).mockResolvedValue({ ...workflow, status: 'REJECTED', completed_at: now })
    renderAt('/approvals/workflow-1')
    await user.click(await screen.findByRole('button', { name: /Reject plan/ }))
    expect(await screen.findByText('Plan rejected')).toBeInTheDocument()
    expect(workspaceApi.decideWorkflow).toHaveBeenCalledWith('workflow-1', 'REJECT')
  })

  it('shows project detail and its task progress', async () => {
    vi.mocked(workspaceApi.project).mockResolvedValue(project)
    vi.mocked(workspaceApi.tasks).mockResolvedValue({ items: [task], total: 1, page: 1, size: 100, pages: 1 })
    renderAt('/projects/project-1')
    expect(await screen.findByRole('heading', { name: 'Customer Portal' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Project tasks' })).toBeInTheDocument()
    expect(screen.getByText('Design API')).toBeInTheDocument()
  })

  it('renders an employee dashboard with workload and status totals', async () => {
    const employee: User = { ...manager, id: 'employee-1', full_name: 'Evan Employee', role: 'EMPLOYEE' }
    renderAt('/', employee)
    expect(await screen.findByRole('heading', { name: 'Welcome back, Evan' })).toBeInTheDocument()
    expect(screen.getByText('Tasks by status')).toBeInTheDocument()
    expect(screen.getByText('Active workload')).toBeInTheDocument()
    expect(screen.getByText('My active projects')).toBeInTheDocument()
  })

  it('filters assigned tasks by status and priority', async () => {
    const user = userEvent.setup()
    const secondTask: Task = { ...task, id: 'task-2', title: 'Build interface', status: 'IN_PROGRESS', priority: 'MEDIUM' }
    vi.mocked(workspaceApi.tasks).mockResolvedValue({ items: [task, secondTask], total: 2, page: 1, size: 100, pages: 1 })
    renderAt('/tasks', { ...manager, id: 'employee-1', role: 'EMPLOYEE' })
    expect(await screen.findByText('Design API')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status'), 'IN_PROGRESS')
    expect(screen.queryByText('Design API')).not.toBeInTheDocument()
    expect(screen.getByText('Build interface')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Priority'), 'HIGH')
    expect(screen.getByText('No tasks match these filters')).toBeInTheDocument()
  })

  it('blocks completion until prerequisites are done and updates valid status', async () => {
    const user = userEvent.setup()
    const prerequisite: Task = { ...task, id: 'task-prerequisite', title: 'Prepare design', status: 'IN_PROGRESS' }
    const dependent: Task = { ...task, id: 'task-dependent', title: 'Build interface', dependencies: [prerequisite.id] }
    vi.mocked(workspaceApi.task).mockImplementation(async id => id === prerequisite.id ? prerequisite : dependent)
    vi.mocked(workspaceApi.updateTaskStatus).mockResolvedValue({ ...dependent, status: 'IN_PROGRESS' })
    renderAt(`/tasks/${dependent.id}`, { ...manager, id: 'employee-1', role: 'EMPLOYEE' })
    await screen.findByRole('heading', { name: 'Build interface' })
    expect(screen.getByRole('option', { name: 'Completed' })).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('New task status'), 'IN_PROGRESS')
    await user.click(screen.getByRole('button', { name: 'Save status' }))
    expect(await screen.findByText('Task status updated to In Progress.')).toBeInTheDocument()
    expect(workspaceApi.updateTaskStatus).toHaveBeenCalledWith(dependent.id, 'IN_PROGRESS')
  })

  it('uses the AI Co-Pilot response and reuses its conversation ID on follow-up', async () => {
    const user = userEvent.setup()
    vi.mocked(workspaceApi.chat)
      .mockResolvedValueOnce({ conversation_id: 'conversation-1', answer: 'Use the project guide.', sources: [{ source: 'guide.md', content: 'Guidance from the project guide.', metadata: { page: 2 }, relevance_score: 0.91 }] })
      .mockResolvedValueOnce({ conversation_id: 'conversation-1', answer: 'The same guide applies.', sources: [] })
    renderAt('/copilot', { ...manager, id: 'employee-1', role: 'EMPLOYEE' })
    const input = await screen.findByLabelText('Ask the AI Co-Pilot')
    await user.type(input, 'Where is the project guide?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText('Use the project guide.')).toBeInTheDocument()
    expect(screen.getByText('guide.md')).toBeInTheDocument()
    await user.type(input, 'Can you clarify?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText('The same guide applies.')).toBeInTheDocument()
    expect(workspaceApi.chat).toHaveBeenNthCalledWith(2, 'Can you clarify?', 'conversation-1')
  })
})
