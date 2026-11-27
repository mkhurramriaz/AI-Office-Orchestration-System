import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, Eye, EyeOff, LockKeyhole, Sparkles } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import type { Department, ProfessionalRole, UserRole } from '../types/api'

const departments: Department[] = ['WEB', 'SEO', 'MARKETING', 'QA', 'AI', 'DESIGN', 'OPERATIONS', 'OTHER']
const professionalRoles: ProfessionalRole[] = ['FRONTEND_DEVELOPER', 'BACKEND_DEVELOPER', 'FULL_STACK_DEVELOPER', 'AI_ENGINEER', 'DATA_ENGINEER', 'DEVOPS_ENGINEER', 'QA_ENGINEER', 'SEO_SPECIALIST', 'DIGITAL_MARKETER', 'UI_UX_DESIGNER', 'PROJECT_MANAGER', 'BUSINESS_ANALYST', 'CONTENT_WRITER', 'OPERATIONS_SPECIALIST']
const label = (value: string) => value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())

function AuthShell({ children, title, subtitle }: { children: React.ReactNode; title: string; subtitle: string }) {
  return <main className="grid min-h-screen bg-white lg:grid-cols-[1.05fr_.95fr]">
    <section className="relative hidden overflow-hidden bg-[#f4f5ff] p-12 lg:flex lg:flex-col lg:justify-between xl:p-16">
      <div className="absolute -left-24 top-1/3 h-96 w-96 rounded-full bg-[#dfe2ff] blur-3xl" /><div className="absolute -bottom-24 right-[-5rem] h-96 w-96 rounded-full bg-[#e9eaff] blur-3xl" />
      <Link to="/login" className="relative flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-brand text-white"><Sparkles size={20} /></span><span className="text-base font-bold">TaskFlow <span className="text-brand">AI</span></span></Link>
      <div className="relative max-w-xl"><div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#dfe1fb] bg-white/70 px-3 py-1.5 text-[11px] font-semibold text-brand"><Sparkles size={13} />Project orchestration, made clear</div><h1 className="text-4xl font-semibold leading-[1.15] tracking-tight text-ink xl:text-5xl">Give your best work a <span className="text-brand">clear path forward.</span></h1><p className="mt-5 max-w-md text-sm leading-7 text-muted">Bring projects, people, and progress into one thoughtful workspace.</p><div className="mt-9 flex items-center gap-4 rounded-2xl border border-white bg-white/75 p-4 shadow-card"><div className="flex -space-x-2"><div className="grid h-8 w-8 place-items-center rounded-full border-2 border-white bg-[#d8e8ff] text-[10px] font-bold text-blue-700">AL</div><div className="grid h-8 w-8 place-items-center rounded-full border-2 border-white bg-[#fce0ce] text-[10px] font-bold text-orange-700">MK</div><div className="grid h-8 w-8 place-items-center rounded-full border-2 border-white bg-[#e9dcff] text-[10px] font-bold text-purple-700">JD</div></div><div><p className="text-xs font-semibold">A calmer way to collaborate</p><p className="mt-1 text-[10px] text-muted">Thoughtful tools for teams that make things happen.</p></div><Check size={17} className="ml-auto text-emerald-500" /></div></div>
      <p className="relative text-[11px] text-muted">© 2026 TaskFlow AI · Made for teams in motion</p>
    </section>
    <section className="flex items-center justify-center px-5 py-12 sm:px-10"><div className="w-full max-w-[420px]"><div className="mb-9 lg:hidden"><Link to="/login" className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-white"><Sparkles size={18} /></span><span className="font-bold">TaskFlow <span className="text-brand">AI</span></span></Link></div><div className="mb-8"><h2 className="text-[27px] font-semibold tracking-tight">{title}</h2><p className="mt-2 text-sm text-muted">{subtitle}</p></div>{children}</div></section>
  </main>
}

function Field({ label: fieldLabel, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label className="block"><span className="mb-2 block text-xs font-medium text-[#454a53]">{fieldLabel}</span><input {...props} className={`h-11 w-full rounded-lg border border-line bg-white px-3.5 text-sm outline-none transition placeholder:text-[#a5a9b1] focus:border-brand focus:ring-4 focus:ring-brand/10 ${props.className ?? ''}`} /></label>
}

function FormError({ message }: { message: string | null }) {
  return message ? <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-xs leading-relaxed text-red-700">{message}</div> : null
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setBusy(true)
    try { await login({ email, password }); navigate(location.state?.from || '/', { replace: true }) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to sign in.') }
    finally { setBusy(false) }
  }
  return <AuthShell title="Welcome back" subtitle="Sign in to pick up right where your team left off.">
    <form onSubmit={submit} className="space-y-5"><Field label="Email address" type="email" autoComplete="email" required placeholder="you@company.com" value={email} onChange={event => setEmail(event.target.value)} /><label className="block"><span className="mb-2 block text-xs font-medium text-[#454a53]">Password</span><span className="relative block"><input className="h-11 w-full rounded-lg border border-line px-3.5 pr-11 text-sm outline-none placeholder:text-[#a5a9b1] focus:border-brand focus:ring-4 focus:ring-brand/10" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required placeholder="Enter your password" value={password} onChange={event => setPassword(event.target.value)} /><button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-3 text-muted" aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span></label><FormError message={error} /><button disabled={busy} className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand text-sm font-semibold text-white shadow-sm transition hover:bg-[#424dd5] disabled:cursor-wait disabled:opacity-60">{busy ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-r-transparent" />Signing in…</> : <>Sign in <ArrowRight size={16} /></>}</button></form>
    <div className="my-7 flex items-center gap-3 text-[10px] text-muted"><span className="h-px flex-1 bg-line" />SECURE WORKSPACE<span className="h-px flex-1 bg-line" /></div><div className="flex items-center justify-center gap-2 text-xs text-muted"><LockKeyhole size={14} /> Protected with your account credentials</div><p className="mt-8 text-center text-sm text-muted">New to TaskFlow? <Link className="font-semibold text-brand hover:underline" to="/register">Create an account</Link></p>
  </AuthShell>
}

export function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'EMPLOYEE' as Exclude<UserRole, 'ADMIN'>, department: 'OTHER' as Department, job_title: '', professional_role: '' as ProfessionalRole | '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setBusy(true)
    try {
      const { professional_role, job_title, ...base } = form
      await register({ ...base, ...(professional_role ? { professional_role } : {}), ...(job_title ? { job_title } : {}) })
      navigate('/', { replace: true })
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to create account.') }
    finally { setBusy(false) }
  }
  const update = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm(previous => ({ ...previous, [key]: value }))
  return <AuthShell title="Create your account" subtitle="Set up your profile and join your team’s workspace.">
    <form onSubmit={submit} className="space-y-3.5"><Field label="Full name" autoComplete="name" required minLength={2} maxLength={255} placeholder="Your name" value={form.full_name} onChange={e => update('full_name', e.target.value)} /><Field label="Work email" type="email" autoComplete="email" required placeholder="you@company.com" value={form.email} onChange={e => update('email', e.target.value)} /><Field label="Password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} placeholder="At least 8 characters" value={form.password} onChange={e => update('password', e.target.value)} /><div className="grid grid-cols-2 gap-3"><label className="block"><span className="mb-2 block text-xs font-medium text-[#454a53]">Account type</span><select value={form.role} onChange={e => update('role', e.target.value as typeof form.role)} className="h-11 w-full rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-brand"><option value="EMPLOYEE">Employee</option><option value="MANAGER">Manager</option></select></label><label className="block"><span className="mb-2 block text-xs font-medium text-[#454a53]">Department</span><select value={form.department} onChange={e => update('department', e.target.value as Department)} className="h-11 w-full rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-brand">{departments.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label></div><Field label="Job title (optional)" maxLength={255} placeholder="e.g. Product designer" value={form.job_title} onChange={e => update('job_title', e.target.value)} /><label className="block"><span className="mb-2 block text-xs font-medium text-[#454a53]">Professional role (optional)</span><select value={form.professional_role} onChange={e => update('professional_role', e.target.value as typeof form.professional_role)} className="h-11 w-full rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-brand"><option value="">Select your specialization</option>{professionalRoles.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label><FormError message={error} /><button disabled={busy} className="mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand text-sm font-semibold text-white transition hover:bg-[#424dd5] disabled:cursor-wait disabled:opacity-60">{busy ? 'Creating account…' : <>Create account <ArrowRight size={16} /></>}</button></form><p className="mt-6 text-center text-sm text-muted">Already have an account? <Link className="font-semibold text-brand hover:underline" to="/login">Sign in</Link></p>
  </AuthShell>
}
