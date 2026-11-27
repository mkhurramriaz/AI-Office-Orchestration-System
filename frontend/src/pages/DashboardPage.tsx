import { useQuery } from '@tanstack/react-query'
import { ArrowRight, BriefcaseBusiness, CheckCircle2, CircleDashed, Clock3, ListTodo } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { getApiError } from '../api/client'
import { workspaceApi } from '../api/workspace'
import type { TaskStatus } from '../types/api'

const statusLabel: Record<TaskStatus, string> = { TODO: 'To do', IN_PROGRESS: 'In progress', BLOCKED: 'Blocked', IN_REVIEW: 'In review', COMPLETED: 'Completed', CANCELLED: 'Cancelled' }
const activeStatuses: TaskStatus[] = ['TODO', 'IN_PROGRESS', 'BLOCKED', 'IN_REVIEW']

export function DashboardPage() {
  const { user } = useAuth()
  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: () => workspaceApi.tasks() })
  const projectsQuery = useQuery({ queryKey: ['projects'], queryFn: workspaceApi.projects })
  const tasks = tasksQuery.data?.items ?? []
  const projects = projectsQuery.data?.items ?? []
  const activeTasks = tasks.filter(task => activeStatuses.includes(task.status)).length
  const activeProjects = projects.filter(project => project.status === 'ACTIVE')
  const grouped = (['TODO', 'IN_PROGRESS', 'BLOCKED', 'IN_REVIEW', 'COMPLETED', 'CANCELLED'] as TaskStatus[]).map(status => ({ status, count: tasks.filter(task => task.status === status).length }))
  const loading = tasksQuery.isPending || projectsQuery.isPending
  const error = tasksQuery.error || projectsQuery.error
  const metricCards = [
    { title: 'Assigned tasks', value: tasksQuery.data?.total ?? '—', helper: 'In your task list', icon: ListTodo, tone: 'bg-indigo-50 text-brand' },
    { title: 'Active workload', value: loading ? '—' : activeTasks, helper: 'Tasks that still need attention', icon: Clock3, tone: 'bg-sky-50 text-sky-600' },
    { title: 'Active projects', value: loading ? '—' : activeProjects.length, helper: 'Projects with work underway', icon: BriefcaseBusiness, tone: 'bg-amber-50 text-amber-600' },
    { title: 'Completed tasks', value: loading ? '—' : grouped.find(item => item.status === 'COMPLETED')?.count ?? 0, helper: 'Your finished work', icon: CheckCircle2, tone: 'bg-emerald-50 text-emerald-600' },
  ]
  const projectMap = new Map(projects.map(project => [project.id, project]))
  return <div>
    <div><p className="text-xs font-medium text-muted">Employee workspace</p><h1 className="mt-2 text-[27px] font-semibold tracking-tight">Welcome back, {user?.full_name.split(' ')[0]}</h1><p className="mt-1 text-sm text-muted">Here’s your workload and what’s moving across your projects.</p></div>
    {error && <div role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{getApiError(error, 'Could not load your workspace.')}</div>}
    <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metricCards.map(({ title, value, helper, icon: Icon, tone }) => <article key={title} className="rounded-xl border border-line bg-white p-5 shadow-card"><span className={`grid h-9 w-9 place-items-center rounded-lg ${tone}`}><Icon size={17} /></span><p className="mt-4 text-xs font-medium text-[#525761]">{title}</p><div className="mt-1 flex items-center gap-2"><strong className="text-[28px] font-semibold tracking-tight">{value}</strong>{loading && <span className="h-3 w-3 animate-spin rounded-full border-2 border-brand border-r-transparent" />}</div><p className="mt-1 text-[10px] text-muted">{helper}</p></article>)}</section>
    <section className="mt-6 rounded-xl border border-line bg-white p-5 shadow-card sm:p-6"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><h2 className="text-sm font-semibold">Tasks by status</h2><p className="mt-1 text-xs text-muted">Your current work, grouped by status</p></div><Link to="/tasks" className="inline-flex items-center gap-1 self-start text-xs font-semibold text-brand">View my tasks <ArrowRight size={14} /></Link></div>
      {tasksQuery.isPending ? <div className="mt-5 h-16 animate-pulse rounded-lg bg-gray-100" /> : tasks.length ? <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">{grouped.map(({ status, count }) => <div key={status} className="rounded-lg bg-[#fafbfc] p-3"><p className="text-[10px] font-medium text-muted">{statusLabel[status]}</p><p className="mt-1 text-lg font-semibold">{count}</p></div>)}</div> : <div className="mt-5 rounded-lg bg-[#fafbfc] px-4 py-8 text-center"><CircleDashed size={22} className="mx-auto text-muted" /><p className="mt-2 text-xs font-semibold">No assigned tasks yet</p><p className="mt-1 text-[10px] text-muted">When a task is assigned to you, it will show up here.</p></div>}
    </section>
    <div className="mt-6 grid gap-5 xl:grid-cols-[1.3fr_1fr]">
      <section className="overflow-hidden rounded-xl border border-line bg-white shadow-card"><div className="flex items-center justify-between border-b border-line px-5 py-4"><div><h2 className="text-sm font-semibold">My tasks</h2><p className="mt-1 text-[11px] text-muted">The next steps assigned to you</p></div><Link to="/tasks" className="text-xs font-semibold text-brand">See all</Link></div>{tasksQuery.isPending ? <div className="space-y-3 p-5">{[1, 2].map(item => <div key={item} className="h-12 animate-pulse rounded-lg bg-gray-100" />)}</div> : tasks.length ? <div className="divide-y divide-line">{tasks.slice(0, 5).map(task => <Link key={task.id} to={`/tasks/${task.id}`} className="flex items-center gap-3 px-5 py-3.5 hover:bg-gray-50"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gray-50 text-muted">{task.status === 'COMPLETED' ? <CheckCircle2 size={16} className="text-emerald-600" /> : <ListTodo size={16} />}</span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{task.title}</span><span className="mt-1 block truncate text-[10px] text-muted">{projectMap.get(task.project_id)?.project_name ?? 'Project'} · {statusLabel[task.status]}</span></span><ArrowRight size={14} className="text-muted" /></Link>)}</div> : <div className="grid min-h-40 place-content-center px-5 text-center"><CheckCircle2 size={22} className="mx-auto text-emerald-500" /><p className="mt-3 text-xs font-semibold">You’re all caught up</p><p className="mt-1 text-[10px] text-muted">Newly assigned work will appear here.</p></div>}</section>
      <section className="overflow-hidden rounded-xl border border-line bg-white shadow-card"><div className="border-b border-line px-5 py-4"><h2 className="text-sm font-semibold">My active projects</h2><p className="mt-1 text-[11px] text-muted">Projects with your assigned tasks</p></div>{projectsQuery.isPending ? <div className="p-5"><div className="h-12 animate-pulse rounded-lg bg-gray-100" /></div> : projectsQuery.error ? <p className="p-5 text-xs text-red-700">{getApiError(projectsQuery.error)}</p> : activeProjects.length ? <div className="divide-y divide-line">{activeProjects.slice(0, 5).map(project => <Link key={project.id} to={`/projects/${project.id}`} className="flex items-center justify-between gap-3 px-5 py-4 hover:bg-gray-50"><span className="min-w-0"><span className="block truncate text-xs font-semibold">{project.project_name}</span><span className="mt-1 block text-[10px] text-muted">{project.task_count} tasks{project.deadline ? ` · Due ${new Date(project.deadline).toLocaleDateString()}` : ''}</span></span><ArrowRight size={14} className="shrink-0 text-muted" /></Link>)}</div> : <div className="grid min-h-40 place-content-center px-5 text-center"><BriefcaseBusiness size={22} className="mx-auto text-muted" /><p className="mt-3 text-xs font-semibold">No active projects</p><p className="mt-1 text-[10px] text-muted">Your active project work will appear here.</p></div>}</section>
    </div>
  </div>
}
