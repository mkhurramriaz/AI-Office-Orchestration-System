import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Activity, Bell, BriefcaseBusiness, Building2, ChevronDown, ClipboardList, LayoutDashboard, LogOut, Menu, ShieldCheck, Users, UserCog, X, Sparkles, ClipboardCheck, Bot } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import type { UserRole } from '../types/api'

const roleLabel: Record<UserRole, string> = { ADMIN: 'Administrator', MANAGER: 'Manager', EMPLOYEE: 'Employee' }
const navigation: { label: string; to: string; icon: typeof LayoutDashboard; roles: UserRole[] }[] = [
  { label: 'Overview', to: '/', icon: LayoutDashboard, roles: ['ADMIN', 'MANAGER', 'EMPLOYEE'] },
  { label: 'Projects', to: '/projects', icon: BriefcaseBusiness, roles: ['ADMIN', 'MANAGER', 'EMPLOYEE'] },
  { label: 'My tasks', to: '/tasks', icon: ClipboardList, roles: ['ADMIN', 'MANAGER', 'EMPLOYEE'] },
  { label: 'AI Co-Pilot', to: '/copilot', icon: Bot, roles: ['ADMIN', 'MANAGER', 'EMPLOYEE'] },
  { label: 'AI approvals', to: '/approvals', icon: ClipboardCheck, roles: ['ADMIN', 'MANAGER'] },
  { label: 'Employees', to: '/admin/employees', icon: UserCog, roles: ['ADMIN'] },
  { label: 'Departments', to: '/admin/departments', icon: Building2, roles: ['ADMIN'] },
  { label: 'Notifications', to: '/admin/notifications', icon: Bell, roles: ['ADMIN'] },
  { label: 'Team', to: '/team', icon: Users, roles: ['MANAGER'] },
  { label: 'Activity', to: '/activity', icon: Activity, roles: ['MANAGER'] },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const visibleNav = navigation.filter(item => user && item.roles.includes(user.role))
  return (
    <div className="min-h-screen bg-canvas text-ink">
      {menuOpen && <button aria-label="Close navigation" className="fixed inset-0 z-20 bg-ink/30 lg:hidden" onClick={() => setMenuOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-30 flex w-[252px] flex-col border-r border-line bg-white transition-transform lg:translate-x-0 ${menuOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex h-[76px] items-center justify-between border-b border-line px-6">
          <NavLink to="/" className="flex items-center gap-3" onClick={() => setMenuOpen(false)}>
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-white"><Sparkles size={19} /></span>
            <span><span className="block text-[15px] font-bold tracking-tight">TaskFlow <span className="text-brand">AI</span></span><span className="block text-[10px] font-semibold uppercase tracking-[.15em] text-muted">Work, in motion</span></span>
          </NavLink>
          <button className="lg:hidden" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={20} /></button>
        </div>
        <div className="px-4 pt-7"><p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[.16em] text-muted">Workspace</p>
          <nav className="space-y-1">{visibleNav.map(({ label, to, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setMenuOpen(false)} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition ${isActive ? 'bg-[#f0f1ff] text-brand' : 'text-[#646a74] hover:bg-gray-50 hover:text-ink'}`}><Icon size={17} strokeWidth={1.8} />{label}</NavLink>)}</nav>
        </div>
        <div className="mt-auto p-4"><div className="rounded-xl border border-line bg-[#fafbfc] p-4"><div className="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-[#eef0ff] text-brand"><ShieldCheck size={16} /></div><p className="text-xs font-semibold">Your workspace is ready</p><p className="mt-1 text-[11px] leading-relaxed text-muted">Your role-based access keeps the right tools close.</p></div></div>
      </aside>
      <div className="lg:pl-[252px]">
        <header className="sticky top-0 z-10 flex h-[76px] items-center justify-between border-b border-line bg-white/95 px-5 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3"><button className="rounded-lg p-2 hover:bg-gray-100 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Open menu"><Menu size={20} /></button><div className="hidden text-xs text-muted sm:block">Workspace <span className="px-2 text-gray-300">/</span><span className="font-medium text-ink">{window.location.pathname.startsWith('/admin/employees') ? 'Employees' : window.location.pathname.startsWith('/admin/departments') ? 'Departments' : window.location.pathname.startsWith('/admin/notifications') ? 'Notifications' : window.location.pathname === '/copilot' ? 'AI Co-Pilot' : window.location.pathname === '/approvals' || window.location.pathname.startsWith('/approvals/') ? 'AI approvals' : window.location.pathname.startsWith('/projects') ? 'Projects' : window.location.pathname.startsWith('/tasks') ? 'Tasks' : 'Overview'}</span></div></div>
          <div className="flex items-center gap-3"><NavLink to={user?.role === 'ADMIN' ? '/admin/notifications' : '/copilot'} aria-label="Notifications" className="relative rounded-lg p-2.5 text-muted hover:bg-gray-50"><Bell size={18} /></NavLink><span className="mx-1 hidden h-8 border-l border-line sm:block" /><div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-full bg-[#e8ebff] text-xs font-bold text-brand">{user?.full_name.split(' ').map(part => part[0]).slice(0, 2).join('').toUpperCase()}</div><div className="hidden min-w-0 sm:block"><p className="max-w-40 truncate text-xs font-semibold">{user?.full_name}</p><p className="mt-0.5 text-[10px] text-muted">{user ? roleLabel[user.role] : ''}</p></div><button onClick={logout} title="Sign out" className="ml-1 rounded-lg p-2 text-muted hover:bg-gray-50 hover:text-ink"><LogOut size={17} /></button><ChevronDown size={14} className="hidden text-muted sm:block" /></div></div>
        </header>
        <main className="mx-auto max-w-[1400px] px-5 py-8 sm:px-8 lg:px-10"><Outlet /></main>
      </div>
    </div>
  )
}
