import React from 'react'

export function Card({ children, className = '', ...props }) {
  return (
    <div
      className={`border border-[#262626] bg-[#121212] overflow-hidden flex flex-col ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '', ...props }) {
  return (
    <div
      className={`px-5 py-3.5 border-b border-[#262626] bg-[#181818] flex items-center justify-between ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardTitle({ children, className = '', ...props }) {
  return (
    <h3
      className={`text-xs mono font-bold text-white tracking-widest uppercase flex items-center gap-2 ${className}`}
      {...props}
    >
      {children}
    </h3>
  )
}

export function CardDescription({ children, className = '', ...props }) {
  return (
    <p className={`text-[10px] mono text-[#737373] mt-0.5 ${className}`} {...props}>
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
      className={`px-5 py-3 border-t border-[#262626] bg-[#0e0e0e] flex items-center justify-between ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
