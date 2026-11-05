export function Loading({ label = 'Đang tải…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-slate-500" data-testid="loading">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600" aria-hidden />
      {label}
    </div>
  )
}

export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-slate-200 ${className}`} data-testid="skeleton" />
}
