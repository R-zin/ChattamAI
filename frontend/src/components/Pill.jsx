import React from 'react'

export default function Pill({ kind = 'info', children, mono = true, dot = true }) {
  return (
    <span className={`status-pill ${kind} ${mono ? 'mono' : ''}`}>
      {dot && <span className="w-1 h-1 rounded-full bg-current" />}
      {children}
    </span>
  )
}
