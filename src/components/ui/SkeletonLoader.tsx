// src/components/ui/SkeletonLoader.tsx

export function TenderCardSkeleton() {
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl border border-slate-200/80 p-5 space-y-4 shadow-sm">
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 flex-1">
          <div className="h-5 bg-slate-200 rounded-md w-3/4 shimmer-skeleton" />
          <div className="h-3 bg-slate-100 rounded-md w-1/3 shimmer-skeleton" />
        </div>
        <div className="h-6 w-20 bg-slate-200 rounded-full shimmer-skeleton" />
      </div>

      {/* Meta tags row */}
      <div className="flex flex-wrap gap-2 pt-1">
        <div className="h-4 w-24 bg-slate-100 rounded shimmer-skeleton" />
        <div className="h-4 w-32 bg-slate-100 rounded shimmer-skeleton" />
        <div className="h-4 w-20 bg-slate-100 rounded shimmer-skeleton" />
      </div>

      {/* Keywords row */}
      <div className="flex items-center gap-1.5 pt-2">
        <div className="h-5 w-16 bg-indigo-50/60 rounded shimmer-skeleton" />
        <div className="h-5 w-20 bg-indigo-50/60 rounded shimmer-skeleton" />
        <div className="h-5 w-14 bg-indigo-50/60 rounded shimmer-skeleton" />
      </div>
    </div>
  )
}

export function SkeletonGrid({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <TenderCardSkeleton key={i} />
      ))}
    </div>
  )
}
