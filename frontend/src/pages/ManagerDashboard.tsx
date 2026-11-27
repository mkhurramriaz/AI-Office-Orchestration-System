import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, BriefcaseBusiness, CheckCircle2, Clock3, ListTodo, Plus, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { getTrackedWorkflowIds, workspaceApi } from '../api/workspace'
import { getApiError } from '../api/client'
import type { WorkflowExecution } from '../types/api'

function useTrackedWorkflows(userId: string) {
  return useQuery({
    queryKey: ['workflows', 'tracked', userId],
    queryFn: async () => {
      const ids = getTrackedWorkflowIds(userId)
      const results = await Promise.allSettled(ids.map(id => workspaceApi.workflow(id)))
      return results.flatMap((result): WorkflowExecution[] => result.status === 'fulfilled' ? [result.value] : [])
    },
    enabled: Boolean(userId),
  })
}

export function ManagerDashboard() {
  const { user } = useAuth()
  const projects = useQuery({ queryKey: ['projects'], queryFn: workspaceApi.projects })
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: () => workspaceApi.tasks() })
  const workflows = useTrackedWorkflows(user?.id ?? '')
  const projectItems = [...(projects.data?.items ?? [])].sort((left, right) => right.created_at.localeCompare(left.created_at))
  const activeTasks = (tasks.data?.items ?? []).filter(task => ['TODO', 'IN_PROGRESS', 'BLOCKED', 'IN_REVIEW'].includes(task.status)).length
  const pending = (workflows.data ?? []).filter(workflow => workflow.status === 'INTERRUPTED').length
  const loading = projects.isPending || tasks.isPending || workflows.isPending
  const error = projects.error || tasks.error
  const metrics = [
    { label: 'Projects', value: loading ? '—' : String(projects.data?.total ?? 0), icon: BriefcaseBusiness, tint: 'bg-indigo-50 text-brand', helper: 'In your workspace' },
    { label: 'Active tasks', value: loading ? '—' : String(activeTasks), icon: ListTodo, tint: 'bg-sky-50 text-sky-600', helper: 'Across your projects' },
    { label: 'Pending approvals', value: loading ? '—' : String(pending), icon: Clock3, tint: 'bg-amber-50 text-amber-600', helper: 'Waiting for your review' },
  ]
  return <div>
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="text-xs font-medium text-muted">Manager workspace</p><h1 className="mt-2 text-[27px] font-semibold tracking-tight">Good to see you, {user?.full_name.split(' ')[0]}</h1><p className="mt-1 text-sm text-muted">Plan projects, review recommendations, and keep delivery moving.</p></div><Link to="/ai/new" className="flex h-10 items-center justify-center gap-2 self-start rounded-lg bg-brand px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-[#424dd5] sm:self-auto"><Plus size={16} /> Create project with AI</Link></div>
    {error && <div role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{getApiError(error, 'Could not load manager overview.')}</div>}
    <section className="mt-8 grid gap-4 md:grid-cols-3">{metrics.map(({ label, value, icon: Icon, tint, helper }) => <article key={label} className="rounded-xl border border-line bg-white p-5 shadow-card"><div className="flex items-center justify-between"><div className={`grid h-10 w-10 place-items-center rounded-xl ${tint}`}><Icon size={18} /></div><span className="text-[10px] font-medium text-muted">Live overview</span></div><p className="mt-5 text-xs font-medium text-[#525761]">{label}</p><div className="mt-1 flex items-baseline gap-2"><p className="text-[30px] font-semibold tracking-tight">{value}</p>{loading && <span className="h-3 w-3 animate-spin rounded-full border-2 border-brand border-r-transparent" />}</div><p className="mt-1 text-[11px] text-muted">{helper}</p></article>)}</section>
    <div className="mt-6 grid gap-5 xl:grid-cols-[1.5fr_1fr]">
      <section className="rounded-xl border border-line bg-white shadow-card"><div className="flex items-center justify-between border-b border-line px-5 py-4 sm:px-6"><div><h2 className="text-sm font-semibold">Recent projects</h2><p className="mt-1 text-xs text-muted">Your latest project work</p></div><Link to="/projects" className="flex items-center gap-1 text-xs font-semibold text-brand">All projects <ArrowRight size={14} /></Link></div>
        {projects.isPending ? <div className="space-y-3 p-6">{[0, 1, 2].map(x => <div key={x} className="h-14 animate-pulse rounded-lg bg-gray-100" />)}</div> : projectItems.length ? <div className="divide-y divide-line">{projectItems.slice(0, 5).map(project => <Link to={`/projects/${project.id}`} key={project.id} className="flex items-center gap-3 px-5 py-4 transition hover:bg-gray-50 sm:px-6"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#f0f1ff] text-brand"><BriefcaseBusiness size={16} /></div><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{project.project_name}</p><p className="mt-1 text-[10px] text-muted">{project.task_count} tasks · {project.status.replaceAll('_', ' ')}</p></div><ArrowUpRight size={15} className="text-muted" /></Link>)}</div> : <div className="grid min-h-56 place-content-center px-5 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-[#f1f2ff] text-brand"><BriefcaseBusiness size={19} /></div><p className="mt-3 text-sm font-semibold">No projects yet</p><p className="mt-1 text-xs text-muted">Start with a brief and AI will prepare a plan for review.</p><Link to="/ai/new" className="mt-4 text-xs font-semibold text-brand">Create your first project <ArrowRight size={13} className="inline" /></Link></div>}
      </section>
      <section className="overflow-hidden rounded-xl border border-line bg-white shadow-card"><div className="border-b border-line px-5 py-4 sm:px-6"><h2 className="text-sm font-semibold">Approval queue</h2><p className="mt-1 text-xs text-muted">AI plans waiting for your decision</p></div>{workflows.isPending ? <div className="p-6"><div className="h-20 animate-pulse rounded-lg bg-gray-100" /></div> : (workflows.data ?? []).filter(w => w.status === 'INTERRUPTED').length ? <div className="divide-y divide-line">{(workflows.data ?? []).filter(w => w.status === 'INTERRUPTED').slice(0, 4).map(workflow => <Link key={workflow.id} to={`/approvals/${workflow.id}`} className="flex items-center gap-3 px-5 py-4 hover:bg-gray-50"><span className="grid h-9 w-9 place-items-center rounded-lg bg-amber-50 text-amber-600"><Clock3 size={16} /></span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{workflow.output_data?.plan?.project_name ?? 'Project plan review'}</span><span className="mt-1 block text-[10px] text-muted">{workflow.output_data?.plan?.tasks.length ?? 0} proposed tasks</span></span><ArrowRight size={14} className="text-muted" /></Link>)}</div> : <div className="grid min-h-44 place-content-center px-5 text-center"><CheckCircle2 size={23} className="mx-auto text-emerald-500" /><p className="mt-3 text-xs font-semibold">You’re all caught up</p><p className="mt-1 text-[10px] text-muted">New project plans will appear here for review.</p></div>}<Link to="/approvals" className="flex items-center justify-center gap-1 border-t border-line py-3 text-xs font-semibold text-brand">Open approvals <ArrowRight size={13} /></Link></section>
    </div>
    <Link to="/ai/new" className="mt-5 flex items-center gap-4 rounded-xl border border-[#e7e8ff] bg-[#f4f5ff] px-5 py-4 transition hover:bg-[#eff0ff]"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-brand"><Sparkles size={18} /></span><span className="min-w-0 flex-1"><span className="block text-xs font-semibold">Turn a brief into an actionable project plan</span><span className="mt-1 block text-[11px] text-muted">Review task dependencies and employee recommendations before approval.</span></span><ArrowRight size={16} className="text-brand" /></Link>
  </div>
}
