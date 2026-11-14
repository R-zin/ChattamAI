import React from 'react'

export function Card({ children, className = '', ...props }) {
  return (
    <div
      className={`border border-line bg-surface overflow-hidden flex flex-col ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '', ...props }) {
  return (
    <div
      className={`px-5 py-3.5 border-b border-line bg-surface-2 flex items-center justify-between ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardTitle({ children, className = '', ...props }) {
  return (
    <h3
      className={`text-xs mono font-bold text-ink tracking-widest uppercase flex items-center gap-2 ${className}`}
      {...props}
    >
      {children}
    </h3>
  )
}

export function CardDescription({ children, className = '', ...props }) {
  return (
    <p className={`text-[10px] mono text-ink-3 mt-0.5 ${className}`} {...props}>
      {children}
    </p>
  )
}

export function CardContent({ children, className = '', ...props }) {
  return (
    <div className={`p-5 flex-1 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({ children, className = '', ...props }) {
  return (
    <div
      className={`px-5 py-3 border-t border-line bg-inset flex items-center justify-between ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
