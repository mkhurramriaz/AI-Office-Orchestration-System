export function LoadingScreen({ label = 'Loading your workspace…' }: { label?: string }) {
  return <div className="flex min-h-screen items-center justify-center bg-canvas text-sm text-muted"><span className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-brand border-r-transparent" />{label}</div>
}
