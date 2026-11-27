import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'

export function UnauthorizedPage() {
  const { user } = useAuth()
  return <div className="mx-auto grid min-h-[60vh] max-w-md place-content-center text-center"><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-amber-50 text-amber-600"><ShieldAlert size={25} /></div><h1 className="mt-5 text-2xl font-semibold">Access unavailable</h1><p className="mt-2 text-sm leading-relaxed text-muted">This section is not available to the <strong>{user?.role}</strong> account. If you need access, ask your workspace administrator.</p><Link to="/" className="mx-auto mt-6 rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white">Back to overview</Link></div>
}
