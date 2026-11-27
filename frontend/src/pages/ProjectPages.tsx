import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, BriefcaseBusiness, CheckCircle2, CircleDashed, LoaderCircle, ListTodo, Save } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getApiError } from '../api/client'
import { workspaceApi } from '../api/workspace'
import type { ProjectStatus, Task, TaskPriority, TaskStatus } from '../types/api'
import { useAuth } from '../auth/AuthProvider'

const projectTone: Record<ProjectStatus, string> = { DRAFT: 'bg-gray-100 text-gray-700', PLANNING: 'bg-blue-50 text-blue-700', ACTIVE: 'bg-emerald-50 text-emerald-700', COMPLETED: 'bg-indigo-50 text-indigo-700', CANCELLED: 'bg-rose-50 text-rose-700' }
const taskTone: Record<TaskStatus, string> = { TODO: 'bg-gray-100 text-gray-700', IN_PROGRESS: 'bg-blue-50 text-blue-700', BLOCKED: 'bg-rose-50 text-rose-700', IN_REVIEW: 'bg-amber-50 text-amber-700', COMPLETED: 'bg-emerald-50 text-emerald-700', CANCELLED: 'bg-gray-100 text-gray-500' }
const priorityTone: Record<TaskPriority, string> = { HIGH: 'text-rose-700', MEDIUM: 'text-amber-700', LOW: 'text-slate-600' }
const humanize = (value: string) => value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, char => char.toUpperCase())

export function ProjectListPage() {
  const { user } = useAuth()
  const projects = useQuery({ queryKey: ['projects'], queryFn: workspaceApi.projects })
  const projectItems = [...(projects.data?.items ?? [])].sort((left, right) => right.created_at.localeCompare(left.created_at))
  return <div><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-medium text-muted">Workspace</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">Projects</h1><p className="mt-1 text-sm text-muted">Browse project plans and delivery progress.</p></div>{user && ['MANAGER', 'ADMIN'].includes(user.role) && <Link to="/ai/new" className="rounded-lg bg-brand px-4 py-2.5 text-xs font-semibold text-white">Create with AI</Link>}</div>
    {projects.isPending ? <div className="mt-10 flex items-center gap-2 text-sm text-muted"><LoaderCircle size={16} className="animate-spin" /> Loading projects…</div> : projects.error ? <div role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{getApiError(projects.error, 'Could not load projects.')}</div> : projectItems.length ? <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{projectItems.map(project => <Link key={project.id} to={`/projects/${project.id}`} className="rounded-xl border border-line bg-white p-5 shadow-card transition hover:-translate-y-0.5 hover:border-[#d3d5f7]"><div className="flex items-start justify-between"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#f0f1ff] text-brand"><BriefcaseBusiness size={18} /></span><span className={`rounded-full px-2.5 py-1 text-[9px] font-semibold ${projectTone[project.status]}`}>{humanize(project.status)}</span></div><h2 className="mt-5 line-clamp-1 text-sm font-semibold">{project.project_name}</h2><p className="mt-2 line-clamp-2 min-h-9 text-[11px] leading-relaxed text-muted">{project.description || 'No project description provided.'}</p><div className="mt-5 flex items-center justify-between border-t border-line pt-4 text-[10px] text-muted"><span>{project.task_count} tasks</span><span>Created {new Date(project.created_at).toLocaleDateString()}</span><ArrowRight size={14} /></div></Link>)}</div> : <div className="mt-7 rounded-xl border border-dashed border-line bg-white px-6 py-16 text-center"><BriefcaseBusiness size={24} className="mx-auto text-brand" /><h2 className="mt-3 text-sm font-semibold">Your projects will show up here</h2><p className="mt-1 text-xs text-muted">Create a project plan and approve it to get started.</p><Link to="/ai/new" className="mt-4 inline-block text-xs font-semibold text-brand">Create a project plan</Link></div>}
  </div>
}

export function ProjectDetailPage() {
  const { user } = useAuth()
  const { projectId = '' } = useParams()
  const project = useQuery({ queryKey: ['project', projectId], queryFn: () => workspaceApi.project(projectId), enabled: Boolean(projectId) })
  const tasks = useQuery({ queryKey: ['tasks', projectId], queryFn: () => workspaceApi.tasks({ project_id: projectId }), enabled: Boolean(projectId) })
  if (project.isPending) return <div className="flex items-center gap-2 py-16 text-sm text-muted"><LoaderCircle size={16} className="animate-spin" /> Loading project…</div>
  if (project.error || !project.data) return <div><Link to="/projects" className="inline-flex items-center gap-2 text-xs text-muted"><ArrowLeft size={14} /> Projects</Link><div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{getApiError(project.error, 'Project could not be loaded.')}</div></div>
  // The employee task endpoint scopes results to the signed-in user and ignores project_id.
  const taskItems = (tasks.data?.items ?? []).filter(task => user?.role !== 'EMPLOYEE' || task.project_id === projectId)
  const completed = taskItems.filter(task => task.status === 'COMPLETED').length
  const percent = taskItems.length ? Math.round(completed / taskItems.length * 100) : 0
  return <div><Link to="/projects" className="inline-flex items-center gap-2 text-xs font-medium text-muted hover:text-ink"><ArrowLeft size={14} /> All projects</Link>
    <div className="mt-6 rounded-xl border border-line bg-white p-5 shadow-card sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><span className={`rounded-full px-2.5 py-1 text-[9px] font-semibold ${projectTone[project.data.status]}`}>{humanize(project.data.status)}</span><h1 className="mt-3 text-2xl font-semibold tracking-tight">{project.data.project_name}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{project.data.description || 'No description provided.'}</p></div><div className="grid h-11 w-11 place-items-center rounded-xl bg-[#f0f1ff] text-brand"><BriefcaseBusiness size={19} /></div></div><div className="mt-6 grid gap-4 border-t border-line pt-5 sm:grid-cols-3"><div><p className="text-[10px] text-muted">Task progress</p><p className="mt-1 text-lg font-semibold">{tasks.isPending ? '—' : `${percent}%`}</p></div><div><p className="text-[10px] text-muted">Tasks complete</p><p className="mt-1 text-lg font-semibold">{tasks.isPending ? '—' : `${completed} / ${taskItems.length}`}</p></div><div><p className="text-[10px] text-muted">Created</p><p className="mt-1 text-sm font-semibold">{new Date(project.data.created_at).toLocaleDateString()}</p></div></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-gray-100"><div className="h-full rounded-full bg-brand transition-all" style={{ width: `${percent}%` }} /></div></div>
    <section className="mt-6 rounded-xl border border-line bg-white shadow-card"><div className="border-b border-line px-5 py-4"><h2 className="text-sm font-semibold">Project tasks</h2><p className="mt-1 text-[11px] text-muted">Status, priority, and prerequisite details</p></div>{tasks.isPending ? <div className="flex items-center gap-2 p-6 text-xs text-muted"><LoaderCircle size={15} className="animate-spin" /> Loading tasks…</div> : tasks.error ? <div role="alert" className="p-5 text-xs text-red-700">{getApiError(tasks.error, 'Could not load project tasks.')}</div> : taskItems.length ? <div className="divide-y divide-line">{taskItems.map(task => <TaskRow key={task.id} task={task} allTasks={taskItems} />)}</div> : <div className="grid min-h-40 place-content-center text-center"><ListTodo size={22} className="mx-auto text-muted" /><p className="mt-3 text-xs font-semibold">No tasks in this project</p></div>}</section>
  </div>
}

export function TaskListPage() {
  const [statusFilter, setStatusFilter] = useState<'ALL' | TaskStatus>('ALL')
  const [priorityFilter, setPriorityFilter] = useState<'ALL' | TaskPriority>('ALL')
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: () => workspaceApi.tasks() })
  const projects = useQuery({ queryKey: ['projects'], queryFn: workspaceApi.projects })
  const projectNames = new Map((projects.data?.items ?? []).map(project => [project.id, project.project_name]))
  const projectItems = tasks.data?.items.filter(task => (statusFilter === 'ALL' || task.status === statusFilter) && (priorityFilter === 'ALL' || task.priority === priorityFilter)) ?? []
  return <div><p className="text-xs font-medium text-muted">Workspace</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">Tasks</h1><p className="mt-1 text-sm text-muted">Track task status, ownership, priority, and dependencies.</p>
    {tasks.isPending ? <div className="mt-8 flex items-center gap-2 text-sm text-muted"><LoaderCircle size={16} className="animate-spin" /> Loading tasks…</div> : tasks.error ? <div role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{getApiError(tasks.error, 'Could not load tasks.')}</div> : <>
      <div className="mt-6 flex flex-col gap-3 rounded-xl border border-line bg-white p-4 sm:flex-row sm:items-end"><label className="text-[11px] font-medium text-muted">Status<select value={statusFilter} onChange={event => setStatusFilter(event.target.value as typeof statusFilter)} className="mt-1 block h-9 w-full min-w-40 rounded-lg border border-line bg-white px-2.5 text-xs text-ink sm:w-auto"><option value="ALL">All statuses</option>{Object.keys(taskTone).map(status => <option value={status} key={status}>{humanize(status)}</option>)}</select></label><label className="text-[11px] font-medium text-muted">Priority<select value={priorityFilter} onChange={event => setPriorityFilter(event.target.value as typeof priorityFilter)} className="mt-1 block h-9 w-full min-w-40 rounded-lg border border-line bg-white px-2.5 text-xs text-ink sm:w-auto"><option value="ALL">All priorities</option>{Object.keys(priorityTone).map(priority => <option value={priority} key={priority}>{humanize(priority)}</option>)}</select></label><p className="text-[10px] text-muted sm:ml-auto">{projectItems.length} tasks</p></div>
      {projectItems.length ? <section className="mt-4 overflow-hidden rounded-xl border border-line bg-white shadow-card"><div className="divide-y divide-line">{projectItems.map(task => <article key={task.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gray-50 text-muted">{task.status === 'COMPLETED' ? <CheckCircle2 size={16} className="text-emerald-600" /> : <CircleDashed size={16} />}</div><div className="min-w-[180px] flex-1"><Link to={`/tasks/${task.id}`} className="text-xs font-semibold hover:text-brand">{task.title}</Link><p className="mt-1 text-[10px] text-muted">{task.task_code} · {projectNames.get(task.project_id) ?? 'Project'} · {humanize(task.department)}</p></div><span className={`rounded-full px-2 py-1 text-[9px] font-semibold ${taskTone[task.status]}`}>{humanize(task.status)}</span><span className={`text-[10px] font-semibold ${priorityTone[task.priority]}`}>{humanize(task.priority)}</span></article>)}</div></section> : <div className="mt-4 rounded-xl border border-dashed border-line bg-white px-6 py-14 text-center"><ListTodo size={23} className="mx-auto text-brand" /><h2 className="mt-3 text-sm font-semibold">{tasks.data?.items.length ? 'No tasks match these filters' : 'No tasks found'}</h2><p className="mt-1 text-xs text-muted">{tasks.data?.items.length ? 'Try selecting a different status or priority.' : 'Tasks assigned to you will appear here.'}</p></div>}
    </>}
  </div>
}

const allowedTaskStatuses: TaskStatus[] = ['TODO', 'IN_PROGRESS', 'BLOCKED', 'IN_REVIEW', 'COMPLETED', 'CANCELLED']

export function TaskDetailPage() {
  const { taskId = '' } = useParams()
  const queryClient = useQueryClient()
  const [nextStatus, setNextStatus] = useState<TaskStatus | ''>('')
  const [notice, setNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const taskQuery = useQuery({ queryKey: ['task', taskId], queryFn: () => workspaceApi.task(taskId), enabled: Boolean(taskId) })
  const task = taskQuery.data
  const projectQuery = useQuery({ queryKey: ['project', task?.project_id], queryFn: () => workspaceApi.project(task!.project_id), enabled: Boolean(task?.project_id) })
  const prerequisiteQueries = useQueries({ queries: (task?.dependencies ?? []).map(id => ({ queryKey: ['task', id], queryFn: () => workspaceApi.task(id) })) })
  const prerequisitesReady = prerequisiteQueries.every(query => query.isSuccess)
  const prerequisiteIncomplete = prerequisiteQueries.some(query => query.data?.status !== 'COMPLETED')
  const update = useMutation({
    mutationFn: (status: TaskStatus) => workspaceApi.updateTaskStatus(taskId, status),
    onSuccess: updated => {
      queryClient.setQueryData(['task', taskId], updated)
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['project', updated.project_id] })
      setNextStatus('')
      setNotice({ kind: 'success', text: `Task status updated to ${humanize(updated.status)}.` })
    },
    onError: error => setNotice({ kind: 'error', text: getApiError(error, 'Could not update the task status.') }),
  })
  if (taskQuery.isPending) return <div className="flex items-center gap-2 py-16 text-sm text-muted"><LoaderCircle size={16} className="animate-spin" /> Loading task…</div>
  if (!task || taskQuery.error) return <div><Link to="/tasks" className="inline-flex items-center gap-2 text-xs text-muted"><ArrowLeft size={14} /> My tasks</Link><div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{getApiError(taskQuery.error, 'Task could not be loaded.')}</div></div>
  const blockedFromCompletion = task.status !== 'COMPLETED' && task.dependencies.length > 0 && (!prerequisitesReady || prerequisiteIncomplete)
  const submitStatus = (event: FormEvent) => { event.preventDefault(); if (nextStatus && !(nextStatus === 'COMPLETED' && blockedFromCompletion)) update.mutate(nextStatus) }
  return <div className="mx-auto max-w-4xl"><Link to="/tasks" className="inline-flex items-center gap-2 text-xs font-medium text-muted hover:text-ink"><ArrowLeft size={14} /> My tasks</Link>
    <div className="mt-6 rounded-xl border border-line bg-white p-5 shadow-card sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[10px] font-semibold uppercase tracking-wider text-muted">{task.task_code} · {projectQuery.data?.project_name ?? 'Project'}</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">{task.title}</h1><p className="mt-2 text-sm leading-6 text-muted">{task.description || 'No task description provided.'}</p></div><span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${taskTone[task.status]}`}>{humanize(task.status)}</span></div>
      <div className="mt-5 flex flex-wrap gap-2"><span className={`rounded-md bg-gray-50 px-2.5 py-1.5 text-[10px] font-semibold ${priorityTone[task.priority]}`}>{humanize(task.priority)} priority</span><span className="rounded-md bg-gray-50 px-2.5 py-1.5 text-[10px] text-gray-600">{humanize(task.department)}</span>{task.required_role && <span className="rounded-md bg-gray-50 px-2.5 py-1.5 text-[10px] text-gray-600">{humanize(task.required_role)}</span>}{projectQuery.data?.deadline && <span className="rounded-md bg-gray-50 px-2.5 py-1.5 text-[10px] text-gray-600">Project deadline {new Date(projectQuery.data.deadline).toLocaleDateString()}</span>}</div>
      {task.dependencies.length > 0 && <section className="mt-6 rounded-lg border border-line p-4"><h2 className="text-xs font-semibold">Prerequisites</h2><div className="mt-2 space-y-2">{task.dependencies.map((id, index) => { const prerequisite = prerequisiteQueries[index]?.data; return <div key={id} className="flex items-center justify-between gap-3 text-xs"><Link to={`/tasks/${id}`} className="text-brand hover:underline">{prerequisite?.title ?? 'Loading prerequisite…'}</Link><span className="text-[10px] text-muted">{prerequisite ? humanize(prerequisite.status) : 'Loading'}</span></div> })}</div></section>}
      {task.acceptance_criteria && <section className="mt-5"><h2 className="text-xs font-semibold">Acceptance criteria</h2><p className="mt-2 whitespace-pre-line text-xs leading-5 text-muted">{task.acceptance_criteria}</p></section>}
      <form onSubmit={submitStatus} className="mt-6 border-t border-line pt-5"><h2 className="text-xs font-semibold">Update status</h2>{blockedFromCompletion && <p role="status" className="mt-2 text-[11px] text-amber-800">Complete all prerequisite tasks before marking this task complete.</p>}{notice && <p role={notice.kind === 'error' ? 'alert' : 'status'} className={`mt-3 rounded-lg px-3 py-2 text-xs ${notice.kind === 'success' ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'}`}>{notice.text}</p>}<div className="mt-3 flex flex-col gap-2 sm:flex-row"><select aria-label="New task status" value={nextStatus} onChange={event => setNextStatus(event.target.value as TaskStatus | '')} className="h-10 rounded-lg border border-line bg-white px-3 text-xs sm:min-w-52"><option value="">Choose a status</option>{allowedTaskStatuses.map(status => <option key={status} value={status} disabled={status === 'COMPLETED' && blockedFromCompletion}>{humanize(status)}</option>)}</select><button disabled={!nextStatus || update.isPending || (nextStatus === 'COMPLETED' && blockedFromCompletion)} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand px-4 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"><Save size={14} />{update.isPending ? 'Saving…' : 'Save status'}</button></div></form>
    </div>
  </div>
}

function TaskRow({ task, allTasks }: { task: Task; allTasks: Task[] }) {
  const taskNames = new Map(allTasks.map(item => [item.id, item.title]))
  return <article className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gray-50 text-muted">{task.status === 'COMPLETED' ? <CheckCircle2 size={16} className="text-emerald-600" /> : <CircleDashed size={16} />}</div><div className="min-w-[180px] flex-1"><p className="text-xs font-semibold">{task.title}</p><p className="mt-1 text-[10px] text-muted">{task.task_code} · {humanize(task.department)}{task.required_role ? ` · ${humanize(task.required_role)}` : ''}</p>{task.dependencies.length > 0 && <p className="mt-1 text-[10px] text-brand">Depends on {task.dependencies.map(id => taskNames.get(id) ?? id).join(', ')}</p>}</div><span className={`rounded-full px-2 py-1 text-[9px] font-semibold ${taskTone[task.status]}`}>{humanize(task.status)}</span><span className={`text-[10px] font-semibold ${priorityTone[task.priority]}`}>{humanize(task.priority)} priority</span><span className="text-[10px] text-muted">{task.assigned_to ? `Assigned · ${task.assigned_to.slice(0, 8)}` : 'Unassigned'}</span></article>
}
