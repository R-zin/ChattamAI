import React from 'react'

export function Skeleton({ className = '', ...props }) {
  return (
    <div
      className={`animate-pulse bg-[#1a1a1a] border border-[#262626] ${className}`}
      aria-hidden="true"
      {...props}
    />
  )
}

export function SkeletonCard({ rows = 3, className = '' }) {
  return (
    <div
      className={`border border-[#262626] bg-[#121212] p-5 space-y-4 ${className}`}
      role="status"
      aria-label="Loading panel"
      aria-busy="true"
    >
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <div className="pt-2 border-t border-[#262626] space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
      <span className="sr-only">Loading card data...</span>
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4, className = '' }) {
  return (
    <div
      className={`border border-[#262626] bg-[#121212] overflow-hidden ${className}`}
      role="status"
      aria-label="Loading table"
      aria-busy="true"
    >
      <div className="px-5 py-3.5 border-b border-[#262626] bg-[#181818] flex items-center justify-between">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="p-4 space-y-3">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex gap-4 items-center">
            {Array.from({ length: cols }).map((_, c) => (
              <Skeleton
                key={c}
                className={`h-4 ${c === 0 ? 'w-1/3' : 'flex-1'}`}
              />
            ))}
          </div>
        ))}
      </div>
      <span className="sr-only">Loading tabular records...</span>
    </div>
  )
}
