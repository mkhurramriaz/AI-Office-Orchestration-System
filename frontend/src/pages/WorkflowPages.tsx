import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Check, CheckCircle2, CircleAlert, LoaderCircle, MessageSquareWarning, Sparkles, X } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { getApiError } from '../api/client'
import { getTrackedWorkflowIds, trackWorkflow, workspaceApi } from '../api/workspace'
import type { PlannedTask, WorkflowExecution, WorkflowStatus } from '../types/api'

const statusText: Record<WorkflowStatus, string> = { PENDING: 'Pending', RUNNING: 'Planning', INTERRUPTED: 'Awaiting approval', COMPLETED: 'Approved and created', REJECTED: 'Rejected', FAILED: 'Planning failed' }
const statusTone: Record<WorkflowStatus, string> = { PENDING: 'bg-gray-100 text-gray-700', RUNNING: 'bg-blue-50 text-blue-700', INTERRUPTED: 'bg-amber-50 text-amber-700', COMPLETED: 'bg-emerald-50 text-emerald-700', REJECTED: 'bg-rose-50 text-rose-700', FAILED: 'bg-red-50 text-red-700' }
const humanize = (value: string) => value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, char => char.toUpperCase())

export function NewAiProjectPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [brief, setBrief] = useState('')
  const start = useMutation({
    mutationFn: workspaceApi.startWorkflow,
    onSuccess: execution => {
      if (user) trackWorkflow(user.id, execution.id)
      void queryClient.invalidateQueries({ queryKey: ['workflows', 'tracked', user?.id] })
      navigate(`/approvals/${execution.id}`)
    },
  })
  const submit = (event: FormEvent) => { event.preventDefault(); start.mutate(brief.trim()) }
  return <div className="mx-auto max-w-3xl">
    <Link to="/" className="inline-flex items-center gap-2 text-xs font-medium text-muted hover:text-ink"><ArrowLeft size={15} /> Manager overview</Link>
    <div className="mt-7"><span className="inline-flex items-center gap-2 rounded-full bg-[#f0f1ff] px-3 py-1.5 text-[11px] font-semibold text-brand"><Sparkles size={13} /> AI project planner</span><h1 className="mt-4 text-3xl font-semibold tracking-tight">What would you like to accomplish?</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Describe the outcome, key features, and constraints. TaskFlow will create a plan and recommend employees for your review.</p></div>
    <form onSubmit={submit} className="mt-7 rounded-2xl border border-line bg-white p-5 shadow-card sm:p-7"><label htmlFor="project-brief" className="text-xs font-semibold">Project brief</label><textarea id="project-brief" value={brief} onChange={event => setBrief(event.target.value)} required minLength={1} maxLength={10000} rows={9} placeholder="For example: Build a customer portal with secure sign-in, account settings, billing history, and an admin reporting dashboard. Launch in phases and include accessibility and QA tasks." className="mt-3 w-full resize-y rounded-xl border border-line bg-[#fcfcfd] p-4 text-sm leading-6 outline-none placeholder:text-gray-400 focus:border-brand focus:ring-4 focus:ring-brand/10" /><div className="mt-2 flex justify-between text-[10px] text-muted"><span>Be clear about the audience and the outcome.</span><span>{brief.length}/10,000</span></div>
      {start.error && <div role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">{getApiError(start.error, 'The project planning workflow could not start.')}</div>}
      {start.isPending && <div className="mt-4 flex items-center gap-3 rounded-lg bg-[#f4f5ff] px-4 py-3 text-xs text-brand"><LoaderCircle size={16} className="animate-spin" /><span><strong className="block">Planning your project…</strong><span className="mt-0.5 block text-[11px] text-[#626bb8]">Generating tasks and checking employee availability. This can take a little while.</span></span></div>}
      <div className="mt-5 flex flex-col justify-between gap-3 border-t border-line pt-5 sm:flex-row sm:items-center"><p className="text-[11px] text-muted">No project or task is created until you approve the finished plan.</p><button disabled={start.isPending || !brief.trim()} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand px-4 text-xs font-semibold text-white hover:bg-[#424dd5] disabled:cursor-not-allowed disabled:opacity-50">{start.isPending ? 'Planning…' : <>Generate plan <ArrowRight size={14} /></>}</button></div>
    </form>
    <div className="mt-4 grid gap-3 sm:grid-cols-3">{[['01', 'Plan', 'AI structures your project brief'], ['02', 'Review', 'Inspect dependencies and recommendations'], ['03', 'Decide', 'Approve to create the project and tasks']].map(([n, title, body]) => <div key={n} className="rounded-xl border border-line bg-white p-4"><span className="text-[10px] font-bold text-brand">{n}</span><p className="mt-2 text-xs font-semibold">{title}</p><p className="mt-1 text-[10px] leading-relaxed text-muted">{body}</p></div>)}</div>
  </div>
}

export function WorkflowListPage() {
  const { user } = useAuth()
  const ids = user ? getTrackedWorkflowIds(user.id) : []
  const workflows = useQuery({
    queryKey: ['workflows', 'tracked', user?.id],
    queryFn: async () => {
      const results = await Promise.allSettled(ids.map(id => workspaceApi.workflow(id)))
      return results.flatMap(result => result.status === 'fulfilled' ? [result.value] : [])
    },
    enabled: Boolean(user),
  })
  return <div><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-medium text-muted">Manager workspace</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">AI plan approvals</h1><p className="mt-1 text-sm text-muted">Review the plans started from this browser.</p></div><Link to="/ai/new" className="inline-flex h-10 items-center justify-center gap-2 self-start rounded-lg bg-brand px-4 text-xs font-semibold text-white"><Sparkles size={15} /> New plan</Link></div>
    {workflows.isPending ? <div className="mt-6 flex items-center gap-2 text-sm text-muted"><LoaderCircle size={16} className="animate-spin" /> Loading approval history…</div> : workflows.error ? <p role="alert" className="mt-6 text-sm text-red-700">{getApiError(workflows.error)}</p> : (workflows.data ?? []).length === 0 ? <div className="mt-7 rounded-xl border border-dashed border-line bg-white px-6 py-16 text-center"><Sparkles size={24} className="mx-auto text-brand" /><h2 className="mt-3 text-sm font-semibold">No plans to review yet</h2><p className="mt-1 text-xs text-muted">Plans you create will be listed here.</p><Link to="/ai/new" className="mt-4 inline-block text-xs font-semibold text-brand">Create an AI plan</Link></div> : <div className="mt-6 grid gap-3">{workflows.data?.map(item => <WorkflowRow key={item.id} workflow={item} />)}</div>}
  </div>
}

function WorkflowRow({ workflow }: { workflow: WorkflowExecution }) {
  return <Link to={`/approvals/${workflow.id}`} className="flex items-center gap-4 rounded-xl border border-line bg-white p-4 shadow-card hover:border-[#d3d5f7] sm:p-5"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#f0f1ff] text-brand"><Sparkles size={17} /></span><span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{workflow.output_data?.plan?.project_name ?? 'Project plan'}</span><span className="mt-1 block truncate text-[11px] text-muted">{workflow.output_data?.plan?.tasks.length ?? 0} tasks · Started {new Date(workflow.created_at).toLocaleDateString()}</span></span><span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${statusTone[workflow.status]}`}>{statusText[workflow.status]}</span><ArrowRight size={15} className="hidden text-muted sm:block" /></Link>
}

export function WorkflowDetailPage() {
  const { workflowId = '' } = useParams()
  const queryClient = useQueryClient()
  const workflow = useQuery({ queryKey: ['workflow', workflowId], queryFn: () => workspaceApi.workflow(workflowId), enabled: Boolean(workflowId) })
  const decision = useMutation({
    mutationFn: (choice: 'APPROVE' | 'REJECT') => workspaceApi.decideWorkflow(workflowId, choice),
    onSuccess: result => {
      queryClient.setQueryData(['workflow', workflowId], result)
      void queryClient.invalidateQueries({ queryKey: ['workflows', 'tracked'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
  if (workflow.isPending) return <div className="flex items-center gap-2 py-16 text-sm text-muted"><LoaderCircle size={17} className="animate-spin" /> Loading plan…</div>
  if (workflow.error || !workflow.data) return <div><Link to="/approvals" className="text-xs text-muted hover:text-ink">← All approvals</Link><div role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{getApiError(workflow.error, 'This workflow could not be loaded. It may not belong to your account.')}</div></div>
  const execution = workflow.data
  const plan = execution.output_data?.plan
  const recommendation = execution.output_data?.recommendations
  const names = new Map((plan?.tasks ?? []).map(task => [task.task_id, task.title]))
  const assignByTask = new Map((recommendation?.assignments ?? []).map(item => [item.task_id, item]))
  const unassignByTask = new Map((recommendation?.unassigned_tasks ?? []).map(item => [item.task_id, item]))
  const canDecide = execution.status === 'INTERRUPTED' && !decision.isPending
  return <div className="mx-auto max-w-5xl">
    <Link to="/approvals" className="inline-flex items-center gap-2 text-xs font-medium text-muted hover:text-ink"><ArrowLeft size={14} /> All approvals</Link>
    <div className="mt-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ${statusTone[execution.status]}`}>{statusText[execution.status]}</span><h1 className="mt-3 text-2xl font-semibold tracking-tight">{plan?.project_name ?? 'Project plan review'}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{plan?.project_description ?? execution.error_message ?? 'Plan details are not available.'}</p></div>{execution.project_id && <Link to={`/projects/${execution.project_id}`} className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-line bg-white px-3 text-xs font-semibold hover:bg-gray-50">Open project <ArrowRight size={14} /></Link>}</div>
    {execution.status === 'FAILED' && <div role="alert" className="mt-5 flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-800"><CircleAlert size={17} className="shrink-0" /><span>{execution.error_message || 'Planning failed. Start a new plan and try again.'}</span></div>}
    {decision.error && <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">{getApiError(decision.error, 'The decision could not be submitted.')}</div>}
    {plan && <>
      <section className="mt-7 rounded-xl border border-line bg-white shadow-card"><div className="flex items-center justify-between border-b border-line px-5 py-4"><div><h2 className="text-sm font-semibold">Project plan</h2><p className="mt-1 text-[11px] text-muted">{plan.tasks.length} proposed tasks · dependencies shown before each task</p></div><span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-medium">{recommendation?.is_fully_assigned ? 'Fully staffed' : `${recommendation?.unassigned_tasks.length ?? 0} unassigned`}</span></div>
        <div className="divide-y divide-line">{plan.tasks.map((task, index) => <PlannedTaskCard key={task.task_id} task={task} index={index} dependencyNames={names} assigned={assignByTask.get(task.task_id)} unassigned={unassignByTask.get(task.task_id)} />)}</div>
      </section>
      {recommendation && <section className="mt-5 rounded-xl border border-line bg-white p-5 shadow-card sm:p-6"><h2 className="text-sm font-semibold">Employee recommendations</h2><p className="mt-1 text-xs text-muted">Recommendations reflect current active workload. No assignments are made until approval.</p>{recommendation.assignments.length ? <div className="mt-4 divide-y divide-line">{recommendation.assignments.map(person => <div key={person.task_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3"><div className="min-w-[180px] flex-1"><p className="text-xs font-semibold">{person.employee_name}</p><p className="mt-1 text-[10px] text-muted">{person.task_title} · {humanize(person.required_role)}</p></div><span className="rounded-md bg-gray-50 px-2 py-1 text-[10px] text-gray-600">{humanize(person.department)}</span><span className="text-[10px] text-muted">Workload {person.current_workload} → {person.projected_workload}</span></div>)}</div> : <p className="mt-4 text-xs text-muted">No employee recommendations were returned.</p>}
        {!!recommendation.unassigned_tasks.length && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4"><p className="flex items-center gap-2 text-xs font-semibold text-amber-900"><MessageSquareWarning size={15} /> Tasks without an eligible employee</p><div className="mt-2 space-y-2">{recommendation.unassigned_tasks.map(item => <div key={item.task_id} className="text-[11px] text-amber-900"><strong>{item.task_title}:</strong> {item.reason}</div>)}</div></div>}</section>}
    </>}
    {execution.status === 'INTERRUPTED' && <div className="sticky bottom-3 z-10 mt-6 flex flex-col justify-between gap-3 rounded-xl border border-[#dedfff] bg-white/95 p-4 shadow-lg backdrop-blur sm:flex-row sm:items-center sm:px-5"><div><p className="text-xs font-semibold">Ready to decide?</p><p className="mt-1 text-[10px] text-muted">Approving creates the project, tasks, dependencies, and recommended assignments.</p></div><div className="flex gap-2"><button onClick={() => decision.mutate('REJECT')} disabled={!canDecide} className="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg border border-line px-3 text-xs font-semibold hover:bg-gray-50 disabled:opacity-50 sm:flex-none"><X size={14} /> Reject plan</button><button onClick={() => decision.mutate('APPROVE')} disabled={!canDecide} className="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg bg-brand px-3 text-xs font-semibold text-white hover:bg-[#424dd5] disabled:opacity-50 sm:flex-none">{decision.isPending ? <><LoaderCircle size={14} className="animate-spin" />Submitting…</> : <><Check size={14} /> Approve & create</>}</button></div></div>}
    {execution.status === 'COMPLETED' && <div className="mt-6 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4"><CheckCircle2 size={19} className="mt-0.5 text-emerald-600" /><div><p className="text-xs font-semibold text-emerald-900">Project approved and created</p><p className="mt-1 text-[11px] text-emerald-800">The project and its tasks have been saved with dependencies and employee assignments.</p>{execution.project_id && <Link to={`/projects/${execution.project_id}`} className="mt-2 inline-block text-xs font-semibold text-emerald-800 underline">View created project</Link>}</div></div>}
    {execution.status === 'REJECTED' && <div className="mt-6 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4"><X size={18} className="mt-0.5 text-rose-600" /><div><p className="text-xs font-semibold text-rose-900">Plan rejected</p><p className="mt-1 text-[11px] text-rose-800">No project or tasks were created from this plan.</p></div></div>}
  </div>
}

function PlannedTaskCard({ task, index, dependencyNames, assigned, unassigned }: { task: PlannedTask; index: number; dependencyNames: Map<string, string>; assigned?: { employee_name: string }; unassigned?: { reason: string } }) {
  return <article className="flex gap-3 px-5 py-4 sm:gap-4 sm:px-6"><div className="flex w-7 shrink-0 flex-col items-center"><span className="grid h-7 w-7 place-items-center rounded-full bg-[#f0f1ff] text-[10px] font-bold text-brand">{index + 1}</span><span className="mt-2 w-px flex-1 bg-line" /></div><div className="min-w-0 flex-1 pb-2"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="text-xs font-semibold">{task.title}</h3><p className="mt-1 text-[11px] leading-relaxed text-muted">{task.description}</p></div><span className={`rounded-full px-2 py-1 text-[9px] font-bold ${task.priority === 'HIGH' ? 'bg-rose-50 text-rose-700' : task.priority === 'MEDIUM' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>{task.priority}</span></div><div className="mt-3 flex flex-wrap gap-1.5"><span className="rounded-md bg-gray-50 px-2 py-1 text-[9px] text-gray-600">{humanize(task.department)}</span><span className="rounded-md bg-gray-50 px-2 py-1 text-[9px] text-gray-600">{humanize(task.required_role)}</span>{task.dependencies.length ? task.dependencies.map(id => <span key={id} className="rounded-md bg-[#f0f1ff] px-2 py-1 text-[9px] text-brand">← {dependencyNames.get(id) ?? id}</span>) : <span className="rounded-md bg-emerald-50 px-2 py-1 text-[9px] text-emerald-700">No prerequisites</span>}</div><div className="mt-3 text-[10px]">{assigned ? <span className="text-emerald-700">Recommended: <strong>{assigned.employee_name}</strong></span> : unassigned ? <span className="text-amber-800">Unassigned: {unassigned.reason}</span> : null}</div></div></article>
}
